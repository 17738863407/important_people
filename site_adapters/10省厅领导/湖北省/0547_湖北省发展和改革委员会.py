from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0547",
    "page_type": "人物列表完整页",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".leader-message",
    "row_selector": ".leader-message li",
    "name_selector": "h4",
    "duty_selector": ".sbdx p",
    "detail_link_selector": "a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "入口直接HTTP请求触发412，online采集需进入无头浏览器；人物信息在渲染后的领导卡片内。",
}


def normalize_text(text: str) -> str:
    """仅压缩字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按渲染后领导卡片的DOM顺序提取姓名、职务和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for card in soup.select(".leader-message li"):
        name_node = card.select_one("h4")
        duty_node = card.select_one(".sbdx p")
        detail_node = card.select_one("a[href]")
        name = normalize_text(name_node.get_text(" ", strip=True) if name_node is not None else "").replace(" ", "")
        duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node is not None else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue

        detail_url = ""
        if detail_node is not None:
            href = normalize_text(detail_node.get("href", ""))
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
