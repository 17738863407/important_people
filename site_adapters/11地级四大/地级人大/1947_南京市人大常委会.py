from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1947",
    "page_type": "职务分组名单页",
    "structure_group": "nanjing_renda_grouped_member_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "chrome",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "nanjing_renda_grouped_member_cards_v1",
    "leader_region_selector": ".left-gzjg-rw",
    "name_selector": ".zcry-top .zcry-name",
    "duty_selector": ".zcry-top .gzjg-rw-tit",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": [".left-gzjg-rw"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "站点HTTP请求偶发403，online需允许无头浏览器兜底",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value).strip("：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按主任、副主任、秘书长、委员分组及DOM顺序输出成员。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".left-gzjg-rw")
    if region is None:
        return []

    records: list[object] = []
    seen: set[str] = set()
    for section in region.select(".zcry-top"):
        duty_node = section.select_one(".gzjg-rw-tit")
        if duty_node is None:
            continue
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not duty or duty == "委员":
            continue
        for name_node in section.select(".zcry-name"):
            name = _clean_text(name_node.get_text(" ", strip=True))
            if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            seen.add(name)
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=page_rule["url"],
                    name=name,
                    duty=duty,
                    detail_url="",
                    evidence=duty,
                    confidence="high",
                    parser=page_rule["parser"],
                    selector_summary=".left-gzjg-rw .zcry-top：标题 + .zcry-name",
                )
            )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
