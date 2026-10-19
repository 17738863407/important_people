from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容site_adapters下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含crawler_core的项目根目录")


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造首页右侧三张领导图片的DeepSeek视觉解析规则。"""
    from crawler_core.vision_llm import build_vision_page_rule

    return build_vision_page_rule(
        rule_id,
        "img[src$='ho_33.jpg'], img#ttyy, img[src$='tyty_03a.jpg']",
        (
            "三张图片依次为常委会主任、常委会副主任、常委会秘书长；"
            "按图片出现顺序及每张图从上到下、从左到右的版面顺序抽取全部姓名，"
            "当一个职务标题对应下方多名人物时，必须为该标题下的每一个姓名分别输出一行，"
            "不得只输出第一人；该组每个人的evidence和visual_span都重复使用从职务标题到本组最后一个姓名的完整连续图片转写原文块，"
            "职务使用图片中明确显示的分组标题，不推断、不补充新闻正文人物。"
        ),
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
    rule_id_value = "1007"
    main(rule_id_value)
