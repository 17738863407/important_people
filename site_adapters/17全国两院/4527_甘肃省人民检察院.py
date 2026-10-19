from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """业务源缺少领导入口时拒绝根据机构名猜测页面或人物。"""
    raise RuntimeError("规则主表缺少领导链接，无法在线定位当前领导页面")


PAGE_RULE = {
    "rule_id": "4527",
    "page_type": "缺少领导入口的安全拒绝适配器",
    "structure_group": "missing_leader_url_safe_failure_v1",
    "reuse_scope": "single_page",
    "load_mode": "无入口，不发起猜测性请求",
    "extract_mode": "explicit_failure",
    "parser": "page_missing_leader_url_safe_failure_v1",
    "leader_region_selector": "",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "规则主表领导链接为空；禁止猜测入口、补名单或使用旧输出兜底",
    "confidence": "low",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """缺少入口时复用统一运行器的失败记录和统一导出契约。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.naming import build_output_name
    from crawler_core.runner import apply_business_location, make_failure_record, prepare_records_for_export

    rule = apply_business_source(PAGE_RULE)
    row = make_failure_record(rule, "规则主表缺少领导链接，无法在线定位当前领导页面")
    row.script_sequence = normalize_script_sequence(rule.get("rule_id"))
    rows = [row]
    apply_business_location(rule, rows)
    prepare_records_for_export(rows)
    output_path = project_dir / "outputs" / build_output_name(str(rule["rule_id"]), str(rule["organization"]))
    export_records(output_path, rows)
    print("实际采集器：未发起（规则主表领导链接为空）")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
