from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    """压缩页面字段中的排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析机构领导表格中连续书写的职务和姓名。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.xxgk-table-list")
    if table is None:
        raise ValueError("未找到机构领导表格 table.xxgk-table-list")

    pattern = re.compile(
        r"^(?P<duty>.*(?:书记|局长|副局长|组长|总工程师|[一二三四五六七八九十]级调研员))"
        r"(?P<name>[一-鿿·]{2,6})$"
    )
    source_url = str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for row in table.select("tbody > tr"):
        link = row.select_one("td.title-td > a[href]")
        if link is None:
            continue
        title = clean_text(link.get("title") or link.get_text(" ", strip=True))
        if not title or title.endswith("领导成员分工"):
            continue
        match = pattern.fullmatch(title)
        if not match:
            continue
        duty = match.group("duty")
        name = match.group("name")
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url or source_url, str(link.get("href", ""))),
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_hefei_public_leader_title_v1",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0085",
    "page_type": "人物列表完整页",
    "structure_group": "hefei_public_leader_table",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "browser_render_wait_ms": 8000,
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_inline_hefei_public_leader_title_v1",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "普通 HTTP 返回 521，online 需进入 Playwright；首行是成员分工汇总而非人物",
    "confidence": "high",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
