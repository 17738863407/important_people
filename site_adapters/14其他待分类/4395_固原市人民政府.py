from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4395",
    "page_type": "government_leader_detail_directory",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "入口为市委人物页；必须从同页侧栏精确定位政府领导分组，再逐人读取详情页标题职务。",
    "confidence": "high",
}


def _request_text(url: str) -> str:
    import requests

    session = requests.Session()
    session.trust_env = False
    response = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按政府领导侧栏顺序提取详情页标题中的姓名和职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    government_group = None
    for group in soup.select("h3.btn"):
        title = group.select_one("a.link > span.name")
        if title and title.get_text(" ", strip=True) == "政府领导":
            government_group = group
            break
    if government_group is None:
        return []

    rows: list[dict[str, str]] = []
    for link in government_group.select("ul li.no_level a[href]"):
        detail_url = link["href"]
        detail = BeautifulSoup(_request_text(detail_url), "html.parser")
        heading = detail.select_one(".zz-ldgl-rt h1")
        duty_node = heading.select_one("span") if heading else None
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
        duty = re.sub(r"^[（(]|[）)]$", "", duty).strip()
        name = ""
        if heading:
            name = "".join(text for text in heading.find_all(string=True, recursive=False)).strip()
            name = re.sub(r"\s+", "", name)
        if name and duty:
            rows.append({"name": name, "duty": duty, "detail_url": detail_url})
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
