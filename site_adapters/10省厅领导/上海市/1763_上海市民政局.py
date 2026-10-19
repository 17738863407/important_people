from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1763",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".table-bordered",
    "item_selector": "ul.uli14 li a[href]",
    "risk_note": "入口为其中一名领导详情页，页面侧栏另含信访接待和局长信箱，必须限定机构领导分组。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def compact_name(value: str) -> str:
    """移除姓名中的全角及普通排版空格。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "")


def comparable_url(value: str) -> str:
    """移除片段并规范末尾斜杠，用于识别入口页自身。"""
    parts = urlsplit(value)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """限定机构领导分组并按列表顺序读取独立姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for header in soup.select(".table-bordered .page-header-1 h2 a"):
        if clean_text(header.get_text(" ", strip=True)) != "机构领导":
            continue
        table = header.find_parent("div", class_="table-bordered")
        if table is None:
            continue

        for link in table.select(page_rule["item_selector"]):
            duty_node = link.select_one("span")
            if duty_node is None:
                continue
            name = compact_name(link.get("title", ""))
            evidence = clean_text(duty_node.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence:
                continue

            candidate_url = urljoin(final_url, link.get("href", "").strip())
            detail_url = "" if comparable_url(candidate_url) == comparable_url(final_url) else candidate_url
            rows.append(
                {
                    "name": name,
                    "duty": "",
                    "evidence": evidence,
                    "detail_url": detail_url,
                }
            )
        break

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
