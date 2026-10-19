from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2712",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".pd_tit ul.ul1",
    "row_selector": ".pd_tit ul.ul1 > li",
    "name_selector": "li > a[href]",
    "duty_selector": "详情页个人简历段中的自治区统计局现职",
    "detail_link_selector": "li > a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "列表仅含姓名链接，职务需按列表顺序逐详情提取；只在当前人物详情的个人简历段内读取以自治区统计局开头、句号前结束的现职。",
}


def normalize_text(text: str) -> str:
    """仅压缩字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def parse_detail(html: str, expected_name: str, detail_url: str) -> dict[str, str] | None:
    """从当前人物详情的个人简历段提取明确现职。"""
    soup = BeautifulSoup(html, "html.parser")
    for paragraph in soup.select(".view p"):
        text = normalize_text(paragraph.get_text(" ", strip=True))
        if not text.startswith("个人简历"):
            continue
        pattern = rf"个人简历[:：]\s*{re.escape(expected_name)}，.*?，(?P<duty>自治区统计局[^。]+)"
        match = re.search(pattern, text)
        if match is None:
            continue
        duty = normalize_text(match.group("duty"))
        return {"name": expected_name, "duty": duty, "detail_url": detail_url, "evidence": duty}
    return None


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按列表DOM顺序动态抓取详情并提取现职。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select(".pd_tit ul.ul1 > li"):
        link = item.select_one("a[href]")
        if link is None:
            continue
        name = normalize_text(link.get_text(" ", strip=True)).replace(" ", "")
        href = normalize_text(link.get("href", ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not href:
            continue

        detail_url = urljoin(final_url, href)
        try:
            detail_html = fetch_html_with_strategy(detail_url, "raw_http").html
            row = parse_detail(detail_html, name, detail_url)
        except Exception:
            continue
        if row is not None:
            rows.append(row)

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
