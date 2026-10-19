from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1078",
    "page_type": "列表转人物详情页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".leader_xx, .leader_xm",
    "risk_note": "历史脚本读取reports快照并硬编码人物详情；现网目录已调整为5人，须逐页在线解析。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2003]+", " ", value or "").strip()


def clean_name(value: str) -> str:
    """移除姓名排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按目录顺序在线读取详情标题中的原始职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    for link in soup.select(".leader_xx a[title][href], .leader_xm a[title][href]"):
        name = clean_name(link.get("title", "") or link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, (link.get("href") or "").strip())
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        result = fetch_html_with_strategy(detail_url, "raw_http")
        detail_soup = BeautifulSoup(result.html, "html.parser")
        heading_node = detail_soup.select_one("h3.fs_h8")
        heading = clean_text(heading_node.get_text(" ", strip=True) if heading_node else "")
        name_pattern = "".join(re.escape(char) + r"\s*" for char in name)
        match = re.fullmatch(rf"(?P<duty>.+?)\s+{name_pattern}", heading)
        if not match:
            continue
        evidence = clean_text(match.group("duty"))
        if not evidence:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": "", "evidence": evidence, "detail_url": result.final_url})
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
