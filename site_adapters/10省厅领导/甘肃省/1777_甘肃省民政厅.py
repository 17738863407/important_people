from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "1777",
    "domain": "mzt.gansu.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_gansu_mzt_leader_cards_v1",
    "leader_region_selector": ".zfxxgk_ldxxlist",
    "name_selector": "a.l_leader_block text first token",
    "duty_selector": "a.l_leader_block text remaining tokens",
    "detail_link_selector": "a.l_leader_block[href]",
    "content_scope": {"start_anchor": "领导信息", "end_anchor": "机构设置", "include_selectors": [".zfxxgk_ldxxlist"], "exclude_selectors": []},
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "browser_dom",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "在线领导信息位于.zfxxgk_ldxxlist，每个a.l_leader_block文本为“姓名 职务”",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".zfxxgk_ldxxlist",
            "name_selector": "a.l_leader_block text first token",
            "duty_selector": "a.l_leader_block text remaining tokens",
            "detail_link_selector": "a.l_leader_block[href]",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "机构设置",
                "include_selectors": [".zfxxgk_ldxxlist"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "在线页面已有完整领导卡片，无需额外接口"},
    },
}


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text)).strip("：:，,。.；;")


def clean_duty(text: str) -> str:
    return normalize_space(text).strip("：:，,。.；;")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def split_leader_text(text: str) -> tuple[str, str]:
    match = re.match(r"(?P<name>[\u4e00-\u9fff·]{2,4})\s+(?P<duty>.+)", normalize_space(text))
    if not match:
        return "", ""
    return clean_name(match.group("name")), clean_duty(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".zfxxgk_ldxxlist")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select("a.l_leader_block[href]"):
        name, duty = split_leader_text(link.get_text(" ", strip=True))
        if not is_name(name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.zfxxgk_ldxxlist；fields=a.l_leader_block text；detail_chain=0",
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
