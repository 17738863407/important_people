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
    """构造协会领导长图的DeepSeek视觉抽取与证据解析规则。"""
    from crawler_core.vision_llm import build_vision_page_rule

    return build_vision_page_rule(
        rule_id=rule_id,
        image_selector="img[src*='tk.File']",
        instruction=(
            "页面正文只有一张纵向协会领导信息长图。严格按图片自上而下、同一行从左到右的版面顺序，"
            "只抽取图片中明确标注的当前协会领导姓名和紧邻职务，不抽取页面导航、相关新闻、二维码或"
            "其他装饰图片。不得依据历史名单、机构常识或旧输出补写。每条evidence和visual_span必须来自"
            "同一人物区域的连续图片原文，能够逐字回指姓名与职务；无法可靠辨认的记录留空并标记低置信，"
            "不得猜测。图片没有人物独立详情链接，detail_url必须为空。"
        ),
    )


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """运行DeepSeek V4 Flash视觉抽取与证据校验。"""
    from crawler_core.vision_llm import parse_vision_llm_records
    from crawler_core.settings import get_settings

    return parse_vision_llm_records(page_rule, html, final_url, get_settings().browser_timeout_seconds)


def main(rule_id: str) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(build_page_rule(rule_id), globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "0223"
    main(rule_id_value)
