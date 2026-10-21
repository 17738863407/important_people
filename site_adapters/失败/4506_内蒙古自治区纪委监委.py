from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4506", "page_type": "CMS内嵌JSON单篇领导机构页",
    "structure_group": "inner_mongolia_discipline_supervision_embedded_json_v1",
    "reuse_scope": "single_page", "load_mode": "静态HTML内嵌JSON",
    "extract_mode": "custom", "parser": "page_inner_mongolia_discipline_supervision_embedded_json_v1",
    "leader_region_selector": "script中的TpmhszUfristPost.data[0].content",
    "name_selector": "内容中的允许角色姓名（当前实时data为空）", "duty_selector": "内容中的角色标签", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page", "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "实时页面由TpmhszUfristPost内嵌JSON填充；2026-10-12在线响应data为空并显示暂无数据，必须明确失败，禁止用历史名单补齐。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """读取页面真实数据源；实时CMS记录为空时保留可追溯失败。"""
    match = re.search(r"var\s+TpmhszUfristPost\s*=\s*(\{.*?\});", html or "", re.DOTALL)
    if match is None:
        raise RuntimeError("实时页面缺少内嵌数据对象TpmhszUfristPost")
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"实时页面内嵌数据对象解析失败：{error}") from error
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or not data:
        raise RuntimeError("实时领导机构页面TpmhszUfristPost.data为空，页面脚本显示“暂无数据”，无可验证人物记录")
    raise RuntimeError("实时领导机构页面数据结构已恢复，需重新核验content DOM后再抽取")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
