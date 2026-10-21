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
    "rule_id": "4287",
    "page_type": "historical_leader_list",
    "load_mode": "http",
    "parser": "custom",
    "risk": "领导介绍目录当前仅列出2022年历史人物条目，未标注现任或更新状态。",
    "confidence": "low",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    if "领导介绍" in html and "22-07-25" in html and "现任" not in html:
        raise RuntimeError("领导介绍入口仅展示2022年历史人物条目，未提供可核验的当前领导名单")
    return []


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
