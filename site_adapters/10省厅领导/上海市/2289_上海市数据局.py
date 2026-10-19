from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2289",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "#news02 .news-list",
    "item_selector": "#news02 .news-list > li.news-item > a.news-content[href]",
    "name_selector": ".news-title",
    "duty_selector": ".news-summary末句",
    "risk_note": "人物摘要首句为基本信息、末句为当前职务，链接为人物详情页。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩摘要排版空白。"""
    return re.sub(r"[\s\u3000\u2003\xa0]+", " ", value or "").strip()


def last_sentence(value: str) -> str:
    """取得摘要末尾非空句并去除纯句末句号。"""
    parts = [part.strip() for part in clean_text(value).split("。") if part.strip()]
    return parts[-1] if parts else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按领导信息卡片顺序提取独立姓名、摘要末句和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for link in soup.select(page_rule["item_selector"]):
        name_node = link.select_one(page_rule["name_selector"])
        summary_node = link.select_one(".news-summary")
        if name_node is None or summary_node is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        evidence = last_sentence(summary_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": urljoin(final_url, link.get("href", "").strip()),
            }
        )

    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
