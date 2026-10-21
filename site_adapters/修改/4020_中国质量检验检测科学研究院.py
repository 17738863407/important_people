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
    "rule_id": "4020",
    "page_type": "院领导页面待检测",
    "structure_group": "caqit_leader_pending_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML预期",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "online",
    "parser": "custom_caqit_leader_pending_v1",
    "risk_flag": "实时请求发生TLS握手失败，未取得可验证页面结构。",
    "confidence": "low",
    "profile_reusable": False,
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """拒绝在未经实时结构核验时猜测人物选择器。"""
    raise RuntimeError("未完成院领导页面实时结构核验，禁止猜测抽取")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
