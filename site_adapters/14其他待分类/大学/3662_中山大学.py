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
    "rule_id": "3662", "page_type": "领导卡片双栏页",
    "structure_group": "sysu_current_leader_cards_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "sysu_current_leader_cards_v1",
    "leader_region_selector": ".nyldlist", "name_selector": "li h4 em",
    "duty_selector": "li h4 span", "detail_link_selector": "",
    "content_scope": {"include_selectors": [".nyldlist"], "exclude_selectors": ["li p"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "党委与行政栏重复校长；卡片正文为分工和邮箱，不属于职务",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """清除纯排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """读取h4中的职务与姓名，忽略同卡片后续分工和邮箱。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    people: dict[str, list[str]] = {}
    for heading in soup.select(".nyldlist li h4"):
        duty_node = heading.select_one(":scope > span")
        name_node = heading.select_one(":scope > em")
        if duty_node is None or name_node is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
            continue
        duties = people.setdefault(name, [])
        for duty in (_clean_text(part) for part in re.split(r"[、；;]", duty_node.get_text(" ", strip=True))):
            if duty and duty not in duties:
                duties.append(duty)
    return [
        PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty="；".join(duties), detail_url="", evidence="；".join(duties),
            confidence="high", parser=page_rule["parser"], selector_summary=".nyldlist li h4 > span + em",
        ) for name, duties in people.items()
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
