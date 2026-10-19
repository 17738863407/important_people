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
    "rule_id": "2741",
    "page_type": "人物列表完整页",
    "structure_group": "leader_link_name_duty_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ShaanxiStatsLeaderCardParser_v1",
    "leader_region_selector": "a[href*='/ldxx/'][title]",
    "name_selector": "title及首个p",
    "duty_selector": "第二个p",
    "detail_link_selector": "a[href*='/ldxx/'][title]",
    "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high",
    "risk_flag": "必须在同一领导链接内配对title与两个段落，禁止读取快照",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """按领导链接顺序提取姓名、职务和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = str(link.get("href", ""))
        if "/ldxx/" not in href or not link.get("title"):
            continue
        name = re.sub(r"\s+", "", _clean_text(str(link.get("title", ""))))
        paragraphs = [_clean_text(node.get_text(" ", strip=True)) for node in link.find_all("p")]
        paragraphs = [text for text in paragraphs if text]
        if len(paragraphs) < 2 or re.sub(r"\s+", "", paragraphs[0]) != name:
            continue
        duty = paragraphs[1]
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
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
                "selector_summary": "a[href含/ldxx/][title]；姓名=title/首个p；职务=第二个p；详情=href",
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
