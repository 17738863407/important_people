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
    "rule_id": "3668", "page_type": "职务分组名单页",
    "structure_group": "swjtu_current_leader_grouped_list_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "swjtu_current_leader_grouped_list_v1",
    "leader_region_selector": ".xdld1", "name_selector": "li > p a[href]",
    "duty_selector": "li > span", "detail_link_selector": "li > p a[href]",
    "content_scope": {"include_selectors": [".xdld1"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_link_only", "max_detail_links": 50},
    "risk_flag": "同一人物跨党委常委与校级职务组；二字姓名含全角字距",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """删除姓名和职务中的纯排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """逐职务组提取并按人物首次出现顺序聚合职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".xdld1")
    if region is None:
        return []
    people: dict[str, dict[str, object]] = {}
    for group in region.select("li"):
        duty_node = group.select_one(":scope > span")
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node is not None else ""
        for anchor in group.select(":scope > p a[href]"):
            name = _clean_text(anchor.get_text(" ", strip=True))
            if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            person = people.setdefault(name, {"duties": [], "detail_url": urljoin(final_url, anchor["href"])})
            if duty not in person["duties"]:
                person["duties"].append(duty)
    return [
        PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty="；".join(person["duties"]), detail_url=person["detail_url"],
            evidence="；".join(person["duties"]), confidence="high", parser=page_rule["parser"],
            selector_summary=".xdld1 li中的直属span与p a[href]",
        ) for name, person in people.items()
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
