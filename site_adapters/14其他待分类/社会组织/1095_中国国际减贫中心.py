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
    """构造当前官方团队长图的DeepSeek视觉证据解析规则。"""
    from crawler_core.vision_llm import build_vision_page_rule

    page_rule = build_vision_page_rule(
        rule_id,
        ".r-con article section[data-type='rtext'] > p > img[data-upload-link]",
        (
            "只抽取长图顶部‘中心领导’区域中配有独立人物照片的领导，保持照片从上到下顺序；"
            "每张照片只对应照片下方紧邻的姓名和完整职务行。遇到下一蓝色处室标题即停止，"
            "不得抽取‘综合处’及其后各处室的处长、副处长、成员或志愿者文字名单；"
            "不得推断、补全或重复人物，evidence和visual_span必须是当前照片下方包含姓名与职务的连续图片转写原文。"
        ),
        fetch_mode="raw_http",
    )
    vision_strategy = page_rule["vision_strategy"]
    if not isinstance(vision_strategy, dict):
        raise RuntimeError("1095视觉规则缺少vision_strategy字典")
    # 长图共六个分块，每批只提交同一横向区域的两块，避免下方处室名单干扰顶部领导姓名识别。
    vision_strategy["tile_batch_size"] = 2
    return page_rule


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """运行DeepSeek V4 Flash视觉抽取及证据回指。"""
    from crawler_core.vision_llm import parse_vision_llm_records
    from crawler_core.settings import get_settings

    return parse_vision_llm_records(page_rule, html, final_url, get_settings().browser_timeout_seconds)


def main(rule_id: str) -> None:
    """运行当前图片人物页面脚本。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(build_page_rule(rule_id), globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "1095"
    main(rule_id_value)
