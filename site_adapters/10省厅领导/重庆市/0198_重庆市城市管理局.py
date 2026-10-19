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
    "rule_id": "0198",
    "domain": "cgj.cq.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "chongqing_jgzn_responsible_cards_v1",
    "reuse_scope": "chongqing_jgzn_pages",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "S023_chongqing_jgzn_card_name_duty_v1",
    "risk_flag": "机构职能页含大量职责与机构噪声；必须由S023限定负责人卡片区域",
    "confidence": "high",
    "locator_strategy": "css",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """沿用专用卡片解析器，仅让依据说明使用已拆分的职务。"""
    from crawler_core.parsers_v1 import chongqing_jgzn_card_name_duty_parser_v1

    rows = chongqing_jgzn_card_name_duty_parser_v1(page_rule, html, final_url)
    for row in rows:
        row.evidence = row.duty
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
