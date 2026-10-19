from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造当前领导表格图片的DeepSeek视觉解析规则。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.vision_llm import build_vision_page_rule

    page_rule = build_vision_page_rule(
        rule_id=rule_id,
        image_selector=".detail .text img[src]",
        instruction=(
            "图片是姓名、性别、职务三列表格。只抽取姓名列及同一行职务列，忽略性别列；"
            "严格按表格自上而下顺序输出；不得把表头识别为人物，不得依据常识、历史名单或旧输出补写；"
            "领导表格中的审判委员会委员、专职委员等委员类人物与职务必须完整保留；"
            "evidence和visual_span必须包含同一行可逐字回指的姓名与完整职务；图片没有人物独立详情链接。"
        ),
        fetch_mode="raw_http",
    )
    strategy = page_rule.get("vision_strategy")
    if isinstance(strategy, dict):
        strategy["tile_edge"] = 3000
    return page_rule


PAGE_RULE = build_page_rule("4554")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """执行视觉转写与证据回指，保留领导表格中的全部人物及完整职务。"""
    from crawler_core.settings import get_settings
    from crawler_core.vision_llm import parse_vision_llm_records

    rows = parse_vision_llm_records(
        page_rule,
        html,
        final_url,
        get_settings().browser_timeout_seconds,
    )
    for row in rows:
        row.detail_url = ""
    if not rows:
        raise RuntimeError("领导表格图片未提取到有效领导记录")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        PAGE_RULE,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
