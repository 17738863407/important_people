from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {"rule_id": "4144", "page_type": "leader_table", "load_mode": "static", "fetch_mode": "online", "parser": "page_specific", "confidence": "high", "risk_notes": "现任领导表格一行可对应多人，同一人员多项职务按表格出现顺序合并。"}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    people: dict[str, dict] = {}
    for row in soup.select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        duty = cells[0].get_text(" ", strip=True)
        links = cells[1].select("a[href]")
        if not duty or not links:
            continue
        for link in links:
            name = "".join(link.get_text(" ", strip=True).split())
            if not name:
                continue
            item = people.setdefault(
                name,
                {"name": name, "duties": [], "detail_url": urljoin(page_url, link["href"])},
            )
            if duty not in item["duties"]:
                item["duties"].append(duty)
    rows = [{"name": item["name"], "duty": "；".join(item["duties"]), "detail_url": item["detail_url"]} for item in people.values()]
    if not rows:
        raise RuntimeError("现任领导表格未解析出姓名和职务")
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
