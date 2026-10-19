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

    return build_vision_page_rule(
        rule_id,
        "img[src*='1790744_a1fa7aa0-9b63-4c9a-9a88-dab185c2c41a.jpg']",
        "只抽取报社领导图片中明确出现的姓名和当前职务，忽略推荐新闻图片。",
        fetch_mode="raw_http",
    )


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
    rule_id_value = "2544"
    main(rule_id_value)
