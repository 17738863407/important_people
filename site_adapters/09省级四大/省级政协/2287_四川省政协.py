from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造当前页面的DeepSeek图片视觉解析规则。"""
    from crawler_core.vision_llm import build_vision_page_rule

    page_rule = build_vision_page_rule(
        rule_id,
        "img[src^='/_img/2026/05/28/']",
        "抽取政协领导图片中明确出现的姓名和职务；同一职务对应多人时逐人输出。"
        "该图片为人物卡片网格：主席之后，副主席须严格按卡片行从左至右、再由上至下排序；"
        "不得按单列从上至下排序，也不得按输入图块顺序排序。",
    )
    vision_strategy = page_rule["vision_strategy"]
    if isinstance(vision_strategy, dict):
        # 原图尺寸适中且为双行卡片网格，整图识别可保留真实行列关系。
        vision_strategy["tile_edge"] = 3000
    return page_rule


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """运行DeepSeek V4 Flash视觉抽取和证据解析。"""
    from crawler_core.vision_llm import parse_vision_llm_records
    from crawler_core.settings import get_settings

    return parse_vision_llm_records(page_rule, html, final_url, get_settings().browser_timeout_seconds)


def main(rule_id: str) -> None:
    """运行当前图片人物脚本。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(build_page_rule(rule_id), globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "2287"
    main(rule_id_value)
