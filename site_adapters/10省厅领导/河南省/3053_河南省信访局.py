from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3053",
    "page_type": "人物列表完整页",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".ldLists",
    "row_selector": ".ldLists li > a[href]",
    "name_selector": ".ldLists li > a[href] > span",
    "duty_selector": "人物链接中全角冒号前文本",
    "detail_link_selector": ".ldLists li > a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "权威入口本身是首位领导详情页；该人的链接等于入口，详情页链接必须留空。当前原始HTML已直出完整侧栏名单。",
}


def normalize_text(text: str) -> str:
    """仅压缩列表字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def canonical_url(url: str) -> str:
    """去除查询、片段并统一末尾斜杠，用于识别入口自身。"""
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按侧栏领导链接的DOM顺序提取职务、姓名及真实详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for link in soup.select(".ldLists li > a[href]"):
        name_node = link.select_one(":scope > span")
        if name_node is None:
            continue
        name = normalize_text(name_node.get_text(" ", strip=True))
        full_text = normalize_text(link.get_text(" ", strip=True))
        if "：" not in full_text:
            continue
        duty = normalize_text(full_text.split("：", 1)[0])
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue

        detail_url = urljoin(base_url, str(link.get("href") or ""))
        if canonical_url(detail_url) == canonical_url(base_url):
            detail_url = ""

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
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
