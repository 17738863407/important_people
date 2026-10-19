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


PAGE_RULE = {"rule_id": "4308", "page_type": "paired_leader_fields", "load_mode": "http", "parser": "custom", "risk": "市长详情页同时展示全体市政府领导，按相邻职务和姓名字段提取。", "confidence": "high"}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for group in soup.select(".m-ld-list2 .leaders"):
        fields = group.find_all("div", recursive=False)
        for duty_node, names_node in zip(fields[::2], fields[1::2]):
            duty = duty_node.get_text(" ", strip=True)
            for link in names_node.select("a.name[href]"):
                name = link.get_text(" ", strip=True)
                key = (name, duty)
                if name and duty and key not in seen:
                    seen.add(key)
                    rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link["href"])})
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
