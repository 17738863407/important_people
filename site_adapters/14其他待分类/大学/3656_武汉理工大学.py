from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3656",
    "page_type": "职务分组名单页",
    "structure_group": "whut_current_leader_grouped_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "whut_current_leader_grouped_list_v1",
    "leader_region_selector": ".ld_list_content",
    "name_selector": ".ld_list_content_item .text_right a[href]",
    "duty_selector": ".ld_list_content_item .text_left",
    "detail_link_selector": ".ld_list_content_item .text_right a[href]",
    "content_scope": {"include_selectors": [".ld_list_content"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_link_only", "max_detail_links": 50},
    "risk_flag": "二字姓名含排版字距，同一人物可能跨党委、纪委和行政职务组",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """删除姓名和职务中的纯排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按职务组顺序提取，并按人物首次出现顺序聚合多项职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".ld_list_content")
    if region is None:
        return []
    people: dict[str, dict[str, object]] = {}
    for group in region.select(".ld_list_content_item"):
        duty_node = group.select_one(".text_left")
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node is not None else ""
        if not duty:
            continue
        for anchor in group.select(".text_right a[href]"):
            name = _clean_text(anchor.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            detail_url = urljoin(final_url, str(anchor.get("href", "")).strip())
            person = people.setdefault(name, {"duties": [], "detail_url": detail_url})
            if duty not in person["duties"]:
                person["duties"].append(duty)

    return [
        PersonRecord(
            organization=page_rule["organization"],
            url=page_rule["url"],
            name=name,
            duty="；".join(person["duties"]),
            detail_url=person["detail_url"],
            evidence="；".join(person["duties"]),
            confidence="high",
            parser=page_rule["parser"],
            selector_summary=".ld_list_content_item: .text_left + .text_right a[href]",
        )
        for name, person in people.items()
    ]


def main(update_fetch_memory: bool) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=update_fetch_memory)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    update_fetch_memory = False
    main(update_fetch_memory)
