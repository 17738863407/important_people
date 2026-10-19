from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1152",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".content",
    "row_selector": ".content li",
    "name_selector": ".content li a[href] > div",
    "duty_selector": ".content li a[href] > p",
    "detail_link_selector": ".content li a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "同一人物可有多个并列职务p，须保留全部非空直接段落及页面顺序，不依赖职务关键词筛选。",
}


def normalize_text(text: str) -> str:
    """仅压缩字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def normalize_name(text: str) -> str:
    """去除姓名中的排版空格。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(text or "")).strip()


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按人物卡片顺序提取姓名及全部非空职务段落。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for item in soup.select(".content li"):
        link = item.select_one("a[href]")
        name_node = item.select_one("a[href] > div")
        if link is None or name_node is None:
            continue
        name = normalize_name(name_node.get_text(" ", strip=True))
        duties = [
            normalize_text(node.get_text(" ", strip=True))
            for node in item.select("a[href] > p")
        ]
        duties = [duty for duty in duties if duty]
        duty = " ".join(duties)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, str(link.get("href") or "")),
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
