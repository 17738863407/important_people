from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1992",
    "page_type": "人物列表完整页",
    "structure_group": "national_railway_department_leader_field_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "parse_page",
    "leader_region_selector": ".list_main.list_bg",
    "name_selector": ".mobile_list_text1中司长冒号后的姓名",
    "duty_selector": ".mobile_list_text1中的司长标签",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "主要领导",
        "end_anchor": "部门职责",
        "include_selectors": [".list_main.list_bg"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "requests",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "官方主要领导字段可能暂未公布姓名",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """只解析官方“主要领导”块中司长字段明确公布的姓名。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    leader_blocks = [
        block
        for block in soup.select(".list_main.list_bg")
        if _clean_text(
            block.select_one("b.mobile_list_titles2").get_text(" ", strip=True)
            if block.select_one("b.mobile_list_titles2")
            else ""
        )
        == "主要领导"
    ]
    if len(leader_blocks) != 1:
        raise RuntimeError(f"官方主要领导块命中数量异常：{len(leader_blocks)}")

    field = leader_blocks[0].select_one(".mobile_list_text1")
    field_text = _clean_text(field.get_text(" ", strip=True) if field else "")
    match = re.fullmatch(r"司长[：:]\s*([\u4e00-\u9fff]{2,4})", field_text)
    if not match:
        if re.fullmatch(r"司长[：:]\s*", field_text):
            raise RuntimeError("官方主要领导字段“司长：”当前未公布姓名")
        raise RuntimeError(f"官方主要领导字段结构异常：{field_text or '空'}")

    name = match.group(1)
    return [
        {
            "name": name,
            "duty": "司长",
            "detail_url": "",
            "evidence": field_text,
            "parser": page_rule["parser"],
            "selector_summary": (
                "strategy=css；leader=.list_main.list_bg中标题为主要领导的唯一块；"
                "name=.mobile_list_text1司长冒号后；duty=司长；detail=无"
            ),
        }
    ]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
