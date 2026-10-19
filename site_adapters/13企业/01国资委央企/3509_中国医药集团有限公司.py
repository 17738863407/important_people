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
    "rule_id": "3509",
    "page_type": "职务分组名单页",
    "structure_group": "国药集团职务多人分组名单",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "SinopharmGroupedRolesParser_v2",
    "leader_region_selector": ".Page_Right .SINOTeam_Div .SINO_Team_List h4",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一人物跨董事会、党委及经理层分组重复出现；按首次顺序聚合明确职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析“职务：多人”节点，并按人物首次出现顺序聚合明确职务。"""
    soup = BeautifulSoup(html, "html.parser")
    duties_by_name: dict[str, list[str]] = {}
    for node in soup.select(".Page_Right .SINOTeam_Div .SINO_Team_List h4"):
        text = _compact_text(node.get_text(" ", strip=True))
        if "：" not in text:
            continue
        group_duty, names_text = text.split("：", 1)
        group_duty = group_duty.strip("，,、；; ")
        if not group_duty:
            continue
        for raw_name in re.split(r"[、,，]", names_text):
            raw_name = raw_name.strip()
            match = re.fullmatch(
                r"(?P<name>[\u4e00-\u9fff·]{2,8})(?:（(?P<extra>[^）]+)）)?",
                raw_name,
            )
            if match is None:
                continue
            name = match.group("name")
            person_duties = duties_by_name.setdefault(name, [])
            for duty in (group_duty, (match.group("extra") or "").strip()):
                if duty and duty not in person_duties:
                    person_duties.append(duty)

    records: list[dict] = []
    for name, duties in duties_by_name.items():
        evidence = "；".join(duties)
        if not evidence:
            continue
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "SINO_Team_List h4；职务：多人；跨分组按首次顺序聚合",
            }
        )
    if not records:
        raise RuntimeError("国药集团职务分组名单未解析到人物记录")
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
