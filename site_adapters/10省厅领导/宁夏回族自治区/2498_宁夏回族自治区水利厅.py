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
    "rule_id": "2498",
    "page_type": "人物列表完整页",
    "structure_group": "ningxia_water_leader_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "leader_region_selector": "a.a[href*='/t'][href$='.html']",
    "confidence": "high",
}


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析宁夏回族自治区水利厅领导简介链接列表。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector = str(page_rule["leader_region_selector"])

    for link in soup.select(selector):
        href = str(link.get("href") or "").strip()
        if not re.search(r"(?:^|/)t\d{8}_\d+\.html$", href):
            continue
        text = _clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<duty>.+?)\s+(?P<name>[\u3400-\u9fff·](?:\s*[\u3400-\u9fff·]){1,3})",
            text,
        )
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = _clean_text(match.group("duty"))
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, href) if href else "",
                "evidence": duty,
                "selector_summary": selector,
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
