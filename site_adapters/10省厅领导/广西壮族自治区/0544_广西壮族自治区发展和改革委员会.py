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
    "rule_id": "0544",
    "page_type": "人物列表完整页",
    "structure_group": "gx_fgw_title_name_duty_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#morelist .more-list",
    "name_selector": ".more-list li a[title][href]",
    "duty_selector": ".more-list li a[title][href]",
    "detail_link_selector": ".more-list li a[title][href]",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "title同时承载姓名和职务，以首段空白为稳定边界",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按委领导列表顺序解析title中的姓名、职务及独立详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    entry_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("#morelist .more-list li a[title][href]"):
        title = _clean_text(link.get("title"))
        parts = re.split(r"\s+", title, maxsplit=1)
        if len(parts) != 2:
            continue
        name, duty = parts
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty or name in seen:
            continue
        detail_url = urljoin(entry_url, str(link.get("href", "")))
        evidence = re.sub(r"[（(]\s*兼\s*[）)]", "", duty)
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
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
