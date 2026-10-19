from __future__ import annotations

import re
import sys
from pathlib import Path

import requests


PAGE_RULE = {
    "rule_id": "0188",
    "page_type": "职务分组名单页",
    "structure_group": "ceaie_secretariat_api_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "requests",
    "extract_mode": "api_field_group",
    "collector": "api_post",
    "parser": "parse_page",
    "leader_region_selector": "#pane-2-1 .leader-title + .el-row .leader4",
    "name_selector": ".name",
    "duty_selector": ".leader-title",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "秘书长",
        "end_anchor": "所属单位",
        "include_selectors": ["#pane-2-1"],
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
    "risk_flag": "接口同时返回历任秘书长、停用记录和测试数据，必须按当前状态及当前职务类型裁剪",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "api": {
        "method": "POST",
        "endpoint": "https://www.ceaie.edu.cn/pc-center/show/secretaryGeneral/getList",
        "data_path": "data",
        "name_field": "secretaryGeneralName",
        "group_field": "dataType",
        "current_status_field": "dataStatus",
    },
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_name(value: object) -> str:
    """清理接口姓名字段中的排版空白。"""
    return re.sub(r"\s+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按当前秘书长、当前副秘书长两个可见分组解析稳定接口。"""
    del html
    api_rule = page_rule["api"]
    response = requests.post(
        api_rule["endpoint"],
        json={},
        timeout=60,
        headers={
            "Accept": "application/json",
            "Referer": final_url,
            "User-Agent": "Mozilla/5.0",
        },
    )
    response.raise_for_status()
    payload = response.json()
    records = payload.get(api_rule["data_path"], [])
    if payload.get("code") != 200 or not isinstance(records, list):
        raise RuntimeError("秘书处人员接口未返回有效data数组")

    duty_by_group = {1: "秘书长", 2: "副秘书长"}
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for group_type in (1, 2):
        for record in records:
            if str(record.get(api_rule["current_status_field"], "")) != "1":
                continue
            try:
                record_group = int(record.get(api_rule["group_field"]))
            except (TypeError, ValueError):
                continue
            if record_group != group_type:
                continue
            name = _clean_name(record.get(api_rule["name_field"]))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen_names:
                continue
            duty = duty_by_group[group_type]
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": "",
                    "evidence": duty,
                    "parser": page_rule["parser"],
                    "selector_summary": (
                        "POST /pc-center/show/secretaryGeneral/getList；"
                        "dataStatus=1；dataType=1秘书长/2副秘书长；"
                        "按页面分组顺序1→2且组内保持接口顺序；页面卡片无人物链接"
                    ),
                }
            )
    if not rows:
        raise RuntimeError("官方接口当前未返回在任秘书长或副秘书长")
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
