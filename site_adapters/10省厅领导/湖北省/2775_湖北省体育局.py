from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2775",
    "page_type": "人物列表完整页",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "div.leader",
    "row_selector": "div.leader a[href]",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "div.leader a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "领导区域同时含纯姓名导航和“姓名 职务”链接；仅接受可严格拆分且职务非空的链接。入口HTTP返回412，online链需浏览器兜底。",
}


def normalize_text(text: str) -> str:
    """仅压缩链接文本中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导区域内含职务链接的DOM顺序提取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div.leader")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select("a[href]"):
        text = normalize_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u4e00-\u9fff·]{2,5})\s+(.+)", text)
        if match is None:
            continue
        name, duty = (normalize_text(part) for part in match.groups())
        name = name.replace(" ", "")
        if name in seen_names:
            continue

        href = normalize_text(link.get("href", ""))
        detail_url = ""
        if href and not href.startswith(("#", "javascript:", "mailto:")):
            detail_url = urljoin(final_url, href)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty})
        seen_names.add(name)

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
