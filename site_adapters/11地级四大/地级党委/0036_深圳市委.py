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
    "rule_id": "0036",
    "page_type": "百度百科半结构领导栏目",
    "load_mode": "动态DOM渲染",
    "extraction_mode": "半结构分组解析",
    "parser": "S027_baidu_baike_leader_section_v1",
    "baike_section_titles": ["市委领导"],
    "confidence": "高",
    "risk_notes": "仅解析指定现任领导栏目，排除历史栏目和图片模块重复名单。",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()

