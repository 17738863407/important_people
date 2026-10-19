from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2773",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".listNc > ul",
    "row_selector": ".listNc > ul > li p",
    "name_selector": ".listNc > ul > li p > a[href]",
    "duty_selector": ".listNc > ul > li p > b",
    "detail_link_selector": ".listNc > ul > li p > a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "页面导航文本较多，领导信息须严格限定在唯一.listNc列表内，保留原始括号和冒号证据。",
}


def normalize_text(text: str) -> str:
    """仅压缩列表字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导列表p的DOM顺序提取职务标签、姓名和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for item in soup.select(".listNc > ul > li p"):
        duty_node = item.select_one("b")
        link = item.select_one("a[href]")
        if duty_node is None or link is None:
            continue
        duty_label = normalize_text(duty_node.get_text(" ", strip=True))
        duty = duty_label.strip("（）()：:，,。；; ")
        name = normalize_text(link.get_text(" ", strip=True))
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
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
