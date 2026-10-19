from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString


PAGE_RULE = {
    "rule_id": "0832",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "ul li.leadPic",
    "row_selector": "li.leadPic",
    "name_selector": ".leadintro h3的直接文本",
    "duty_selector": ".leadintro > p:nth-of-type(2)",
    "detail_link_selector": "a.leader-img[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "姓名h3内同时含“更多”链接，必须只取h3直接文本；职务取【职务】标签后的第二个直接p。",
}


def normalize_text(text: str) -> str:
    """确定性清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ")).strip()


def direct_text(node: object) -> str:
    """读取标签的直接文本，排除其内“更多”等链接文字。"""
    if node is None or not hasattr(node, "contents"):
        return ""
    return normalize_text(" ".join(str(child) for child in node.contents if isinstance(child, NavigableString)))


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按委领导卡片顺序提取强结构字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for card in soup.select("li.leadPic"):
        name = direct_text(card.select_one(".leadintro h3"))
        duty_node = card.select_one(".leadintro > p:nth-of-type(2)")
        detail_link = card.select_one("a.leader-img[href]")
        duty = normalize_text(duty_node.get_text(" ", strip=True)).rstrip("。 ") if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or not duty:
            continue

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": (
                    urljoin(base_url, str(detail_link.get("href") or ""))
                    if detail_link is not None
                    else ""
                ),
                "evidence": duty,
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
