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

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """解析人员组成页中的有名人物卡片，排除姓名为空的职务栏目。"""
    soup = BeautifulSoup(html or "", "html.parser")
    records: list[dict] = []
    seen: set[str] = set()

    for card in soup.select(".listChangeDiv .nr"):
        role_node = card.select_one("dl > dt > a")
        name_node = card.select_one("dl > dd > a")
        role = clean_text(role_node.get_text(" ", strip=True) if role_node else "")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        if not role or not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        seen.add(name)
        href = str(name_node.get("href") or "")
        records.append(
            {
                "name": name,
                "duty": role,
                "detail_url": urljoin(final_url, href) if href else "",
                "evidence": role,
                "confidence": "high",
                "parser": "page_inline_qingdao_cppcc_role_cards_v1",
            }
        )

    return records


PAGE_RULE = {
    "rule_id": "2124",
    "page_type": "人物列表完整页",
    "structure_group": "qingdao_cppcc_role_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_qingdao_cppcc_role_cards_v1",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "页面同时保留多个姓名为空的职务栏目，仅输出当前具有明确姓名链接的卡片",
    "confidence": "high",
}


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
