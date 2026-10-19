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
    "rule_id": "2168",
    "page_type": "职务分组名单页",
    "structure_group": "nanning_people_congress_group_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "nanning_people_congress_group_cards_v2",
    "leader_region_selector": ".detail-content-c .rdcwh",
    "name_selector": "span",
    "duty_selector": "h5",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "姓名节点包含性别和民族括注，解析时仅做确定性括注剥离",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_name(value: str) -> str:
    """清理卡片姓名中的排版空白，并移除性别、民族括注。"""
    name = re.split(r"[（(]", value, maxsplit=1)[0]
    return re.sub(r"[\s\u3000\xa0]+", "", name)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按页面职务分组和人物卡片的原始DOM顺序抽取。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    records: list[object] = []
    for group in region.find_all("div", recursive=False):
        duty_node = group.find("h5", recursive=False)
        if duty_node is None:
            continue
        duty = " ".join(duty_node.stripped_strings)
        duty = re.sub(r"\d+人\s*[（(]\s*按姓氏笔划排序\s*[）)]", "", duty).strip()
        if not duty or duty == "委员":
            continue
        for name_node in group.select(":scope > div > span"):
            name = _clean_name(name_node.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,12}", name):
                continue
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
