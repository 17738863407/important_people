from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0826",
    "page_type": "人物列表完整页",
    "structure_group": "gx_sasac_heading_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".gov-site-right .second-gird",
    "name_selector": "h2 strong",
    "duty_selector": "h2 strong",
    "detail_link_selector": "h2 + ul.txt-list a[href]",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "侧栏另有领导链接；仅使用正文h2强标题及其后续个人文章列表",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文领导标题顺序绑定其后首个个人详情文章。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    entry_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for strong in soup.select(".gov-site-right .second-gird h2.more-chlid-title strong"):
        title = _clean_text(strong.get_text(" ", strip=True))
        if "_" not in title:
            continue
        name, duty = (_clean_text(value) for value in title.split("_", 1))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty or name in seen:
            continue
        heading = strong.find_parent("h2")
        detail_list = heading.find_next("ul", class_="txt-list") if heading else None
        detail_link = detail_list.select_one("a[href]") if detail_list else None
        if detail_link is None or _clean_text(detail_link.get_text(" ", strip=True)) != name:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(entry_url, str(detail_link.get("href", ""))),
            }
        )

    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
