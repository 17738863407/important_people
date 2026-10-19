from __future__ import annotations

import sys
from pathlib import Path
import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4572",
    "page_type": "失效领导详情入口",
    "structure_group": "xinjiang_high_court_missing_leader_page_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "extract_mode": "custom",
    "parser": "page_xinjiang_high_court_missing_v1",
    "leader_region_selector": "规则主表入口当前重定向至error.shtml；站点当前领导栏目列表为空",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "入口HTTP 404且当前权威领导栏目为空；不得从新闻报道拼接人物名单。入口恢复后须按真实领导区域重建解析，委员和专职委员不得排除。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """在线确认权威入口状态；失效时输出可复核的明确失败。"""
    url = str(page_rule.get("url") or "").strip()
    if not url:
        raise RuntimeError("规则主表领导链接为空，无法在线核验领导页面")
    response = requests.get(
        url, timeout=30, verify=False,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    if response.status_code == 404 or response.url.rstrip("/").endswith("/error.shtml"):
        raise RuntimeError(
            "规则主表领导入口已重定向至站点error.shtml并返回HTTP 404；"
            "在线核验的新疆高院领导介绍栏目当前列表为空，无法形成可验证名单"
        )
    response.raise_for_status()
    raise RuntimeError("规则主表领导入口已恢复响应，但页面没有可验证的领导人物结构")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
