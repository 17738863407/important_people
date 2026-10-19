from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1293",
    "page_type": "职务分组名单页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".content",
    "row_selector": ".content .detail, .content .row li",
    "name_selector": ".detail h1, li h2",
    "duty_selector": ".detail h1, li h2 + p",
    "detail_link_selector": "a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "首位人物以“职务：姓名”合并在h1，其余人物为h2姓名+p职务；入口HTTP返回412，online链当前需Chrome CDP兜底。",
}


def normalize_text(text: str) -> str:
    """仅压缩字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def valid_detail_url(base_url: str, href: str) -> str:
    """只转换当前卡片中的有效人物链接。"""
    value = normalize_text(href)
    if not value or value.startswith(("#", "javascript:", "mailto:")):
        return ""
    return urljoin(base_url, value)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按首位详情块和后续卡片的页面顺序提取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    detail = soup.select_one(".content .detail")
    if detail is not None:
        heading = detail.select_one("h1")
        link = detail.select_one("a[href]")
        text = normalize_text(heading.get_text(" ", strip=True) if heading is not None else "")
        match = re.fullmatch(r"(.+?)[：:]([\u4e00-\u9fff·]{2,5})", text)
        if match is not None:
            duty, name = (normalize_text(part) for part in match.groups())
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": valid_detail_url(final_url, link.get("href", "") if link is not None else ""),
                    "evidence": duty,
                }
            )

    for card in soup.select(".content .row li"):
        name_node = card.select_one("h2")
        duty_node = card.select_one("h2 + p")
        link = card.select_one("a[href]")
        name = normalize_text(name_node.get_text(" ", strip=True) if name_node is not None else "").replace(" ", "")
        duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node is not None else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": valid_detail_url(final_url, link.get("href", "") if link is not None else ""),
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
