from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3995",
    "page_type": "基金会领导简介列表页",
    "structure_group": "cepf_leader_detail_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_cepf_leader_detail_list_v1",
    "leader_region_selector": ".col_list_txt",
    "name_selector": "li > a[href$='.html']",
    "duty_selector": "详情正文现任句",
    "detail_link_selector": "li > a[href$='.html']",
    "content_scope": {"start_anchor": "领导简介", "end_anchor": "Copyright", "include_selectors": [".col_list_txt"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "dynamic_detail_page"},
    "risk_flag": "列表页仅展示姓名，必须逐个动态读取其独立简介页的现任句。",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验列表两名领导均有独立详情页，现职仅在正文末尾现任句中。",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".col_list_txt", "name_selector": "li > a[href$='.html']", "detail_link_selector": "li > a[href$='.html']"}, "api": {"enabled": False, "reason": "当前HTML列表及详情正文已完整提供人物信息"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def fetch_detail_text(detail_url: str) -> str:
    """直连读取当前人物详情页，避免继承失效本地代理。"""
    session = requests.Session()
    session.trust_env = False
    response = session.get(detail_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    return clean_text(BeautifulSoup(response.content, "html.parser").get_text(" ", strip=True))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按列表顺序提取姓名，并从各自简介页读取明确的现任职务。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".col_list_txt")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in root.select("li > a[href$='.html']"):
        name = clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, link.get("href", ""))
        detail_text = fetch_detail_text(detail_url)
        match = re.search(r"(?:现任|至今任)\s*(.+?)(?:。|$)", detail_text)
        if match is None:
            continue
        duty = clean_text(match.group(1)).rstrip("。")
        if not duty:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": ".col_list_txt 人物链接 + 详情正文现任句"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
