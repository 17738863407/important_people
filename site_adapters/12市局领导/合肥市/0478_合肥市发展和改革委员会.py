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
    "rule_id": "0478",
    "page_type": "人物列表完整页",
    "structure_group": "hefei_public_leader_title_list",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "leader_region_selector": "table.xxgk-table-list > tbody",
    "detail_link_selector": ":scope > tr > td.title-td > a.title[href]",
    "risk_flag": "首行是领导分工总览；人物标题为姓名与职务无分隔连续文本",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


ROLE_BOUNDARY = (
    "派驻|总会计师|总工程师|总经济师|副主任|主任|党组|党委|党工委|"
    "一级调研员|二级调研员|三级调研员|四级调研员|巡视员"
)


def split_name_duty(title: str) -> tuple[str, str]:
    """按职务关键词边界拆分无分隔的“姓名＋职务”标题。"""
    compact = re.sub(r"\s+", "", title or "")
    match = re.fullmatch(
        rf"(?P<name>[一-鿿·]{{2,4}}?)(?P<duty>(?:{ROLE_BOUNDARY}).*)",
        compact,
    )
    if match is None:
        return "", ""
    return match.group("name"), match.group("duty")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析机构领导表格中的人物标题和真实详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select("table.xxgk-table-list > tbody > tr > td.title-td > a.title[href]"):
        title = str(link.get("title") or link.get_text(" ", strip=True))
        name, duty = split_name_duty(title)
        detail_url = urljoin(final_url, str(link.get("href") or "").strip())
        if not name or not duty or not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_hefei_public_leader_title_list_v1",
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
