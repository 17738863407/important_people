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
    "rule_id": "4580",
    "page_type": "法院检察院领导页面待核验",
    "structure_group": "provincial_court_4580_pending_v1",
    "reuse_scope": "single_page",
    "load_mode": "在线页面待核验",
    "extract_mode": "custom",
    "parser": "page_provincial_court_4580_pending_v1",
    "leader_region_selector": "未经实时页面核验，不猜测选择器",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "low",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "执行环境未取得可验证页面结构，禁止使用历史名单或猜测解析规则；页面恢复并确认领导区域后，审判委员会委员、专职委员及仅任委员者均须保留。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """实际尝试权威入口；缺链接或请求失败时拒绝猜测人物结果。"""
    url = str(page_rule.get("url") or "").strip()
    if not url:
        raise RuntimeError("规则主表领导链接为空，无法在线核验领导页面")
    session = requests.Session()
    session.trust_env = False
    try:
        response = session.get(
            url, timeout=30, verify=False,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise RuntimeError(f"在线页面核验失败，未建立解析规则：{error}") from error
    raise RuntimeError("在线页面已响应但尚未完成DOM人工核验，禁止猜测抽取")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
