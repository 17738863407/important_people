from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0682",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "div.leader ul.list-b",
    "row_selector": "div.leader ul.list-b > li",
    "name_selector": "h4 a",
    "duty_selector": "h4 + p",
    "detail_link_selector": "h4 a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "卡片含较长分工及信箱内容；必须仅读取h4后的直属职务段落。",
}


def normalize_text(text: str) -> str:
    """仅压缩字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片DOM顺序提取姓名、直属职务段落和人物详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for card in soup.select("div.leader ul.list-b > li"):
        name_node = card.select_one("h4 a")
        duty_node = card.select_one("h4 + p")
        name = normalize_text(name_node.get_text(" ", strip=True) if name_node is not None else "").replace(" ", "")
        duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node is not None else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue

        detail_url = ""
        if name_node is not None:
            href = normalize_text(name_node.get("href", ""))
            if href and not href.startswith(("#", "javascript:", "mailto:")):
                detail_url = urljoin(final_url, href)

        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty})

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
