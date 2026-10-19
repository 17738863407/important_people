from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1884",
    "domain": "www.neac.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "neac_society_org_people",
    "reuse_scope": "neac_society_pages",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "S017_neac_main_society_org_people_v1",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文后存在大量国务院部门、地方政府和直属单位链接，必须使用国家民委主管社团机构人员专用解析器限定正文角色分组",
    "confidence": "high",
    "filter_policy": "weak_allow_wordlist",
    "locator_strategy": "legacy_css",
    "locator": {
        "api": {
            "enabled": False,
            "reason": "当前静态HTML正文直接列出副会长和秘书长名单",
        },
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "online_verified_20260806",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
