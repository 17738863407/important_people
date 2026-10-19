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
    "rule_id": "2513",
    "page_type": "人物列表完整页",
    "structure_group": "leader_link_name_duty_responsibility",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ShaanxiEnergyLeaderLinkParser_v1",
    "leader_region_selector": "a[href$='.html']",
    "name_selector": "链接文本开头姓名",
    "duty_selector": "姓名后至主持/分管前文本",
    "detail_link_selector": "a[href$='.html']",
    "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high",
    "risk_flag": "领导链接同时包含职务和分工，依据只保留主持/分管前的职务文本",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """按领导链接顺序提取姓名、职务和详情页，排除后续分工。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = str(link.get("href", ""))
        if not href.endswith(".html"):
            continue
        text = _clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<name>[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff]){1,3})\s+"
            r"(?P<duty>(?:省发展改革委|省能源局).+?)(?:\s+(?:主持|分管).*)?",
            text,
        )
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = _clean_text(match.group("duty"))
        if not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": "",
                "detail_url": urljoin(base_url, href),
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "领导a[href$=.html]；姓名=链接开头；职务=姓名后至主持/分管前文本",
                "order": str(len(records) + 1),
            }
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
