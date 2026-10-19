from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0452",
    "page_type": "人物列表完整页",
    "structure_group": "gz_geology_list_detail_labels_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".scroll_main1 .zfxxgk_zdgkc",
    "name_selector": ".scroll_main1 .zfxxgk_zdgkc dd a[title][href]",
    "duty_selector": "详情页姓名、职务、领导分工标签区间",
    "detail_link_selector": ".scroll_main1 .zfxxgk_zdgkc dd a[title][href]",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "部分当前详情的职务字段可能为空；保留可验证姓名但不推断职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def _extract_labels(html: str, list_name: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    text = _clean_text(soup.get_text(" ", strip=True))
    name_match = re.search(r"姓名[：:]\s*([\u4e00-\u9fff·]{2,8})", text)
    duty_match = re.search(r"职务[：:]\s*(.*?)\s*领导分工", text)
    name = _clean_text(name_match.group(1)) if name_match else list_name
    duty = _clean_text(duty_match.group(1)).strip("。") if duty_match else ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导窗口顺序在线请求详情并读取姓名、职务标签字段。"""
    import requests
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    entry_url = final_url or page_rule["url"]
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    selector = ".scroll_main1 .zfxxgk_zdgkc dd a[title][href]"
    for link in soup.select(selector):
        list_name = re.sub(r"\s+", "", _clean_text(link.get("title") or link.get_text("", strip=True)))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", list_name) is None or list_name in seen:
            continue
        detail_url = urljoin(entry_url, str(link.get("href", "")))
        try:
            response = session.get(detail_url, timeout=25)
            response.raise_for_status()
        except requests.RequestException:
            continue
        response.encoding = response.apparent_encoding or response.encoding
        name, duty = _extract_labels(response.text, list_name)
        if name != list_name or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": response.url,
            }
        )

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
