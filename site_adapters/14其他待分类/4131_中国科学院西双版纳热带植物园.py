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


PAGE_RULE = {
    "rule_id": "4131",
    "page_type": "leader_cards",
    "load_mode": "static",
    "fetch_mode": "online",
    "parser": "page_specific",
    "confidence": "high",
    "risk_notes": "当前领导卡片的任职字段为明确结构，部分人员未提供详情链接。",
}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    """从当前领导卡片的姓名链接和“任职”字段提取记录。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select("div.nei_yjy_info div.nei_ldjs_info_top"):
        name_link = card.select_one("a.nei_xrld_title")
        duty_node = card.select_one("p.nei_xrld_span span:nth-of-type(2)")
        if name_link is None or duty_node is None:
            continue
        name = name_link.get_text(" ", strip=True)
        duty = duty_node.get_text(" ", strip=True)
        if not name or not duty:
            continue
        href = name_link.get("href", "").strip()
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(page_url, href) if href else "",
            }
        )
    if not rows:
        raise RuntimeError("现任领导卡片未解析出姓名和任职字段")
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
