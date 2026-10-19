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


PAGE_RULE = {"rule_id": "4310", "page_type": "leader_cards_with_detail_titles", "load_mode": "http", "parser": "custom", "risk": "入口卡片不展示职务，逐个读取可验证人物详情页标题的现职字段。", "confidence": "high"}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup
    import requests

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.trust_env = False
    rows: list[dict[str, str]] = []
    for link in soup.select(".zf-detail .leader-container a[href]"):
        name_node = link.select_one(".leader-name")
        if name_node is None:
            continue
        detail_url = link["href"]
        response = session.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25, verify=False)
        response.raise_for_status()
        detail = BeautifulSoup(response.content, "html.parser")
        title = detail.title.get_text(" ", strip=True) if detail.title else ""
        duty = re.split(r"[-—]昭通市人民政府", title, maxsplit=1)[0].strip()
        name = name_node.get_text(" ", strip=True)
        if name and duty:
            rows.append({"name": name, "duty": duty, "detail_url": response.url})
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
