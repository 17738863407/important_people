from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1966",
    "page_type": "多人物详情合并页",
    "structure_group": "notcsoa_current_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".c_right ul.leader",
    "name_selector": "li .font_box h4",
    "duty_selector": "li .font_box p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页左栏含栏目导航，页脚含机构地址",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """清理网页排版空白。"""
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按现任领导卡片DOM顺序提取姓名和原始职务。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    for card in soup.select(".c_right ul.leader > li"):
        name_node = card.select_one(".font_box h4")
        duty_node = card.select_one(".font_box p")
        if name_node is None or duty_node is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        duty = _clean_text(duty_node.get_text(" ", strip=True))
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
                selector_summary="c_right现任领导卡片h4姓名p职务",
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
