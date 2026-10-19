from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def build_page_rule(rule_id: str) -> dict[str, object]:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.vision_llm import build_vision_page_rule
    return build_vision_page_rule(
        rule_id=rule_id,
        image_selector=".TRS_Editor img[src^='./W020']",
        instruction=(
            "页面正文按DOM顺序包含云南省人民检察院现任领导信息图片。逐图只抽取图片中明确出现的姓名和完整当前职务，"
            "严格保持图片及图片内自上而下、从左到右的顺序；不得依据历史名单、旧输出或常识补写。"
            "图片领导区域内的检察委员会委员、检察委员会专职委员及其他委员类人物必须与其他领导一样完整抽取，"
            "不得删除委员类职务或因仅任委员而排除人物。evidence和visual_span必须含同一人物的姓名及完整职务；"
            "图片没有人物独立详情链接。"
        ),
        fetch_mode="raw_http",
    )


PAGE_RULE = build_page_rule("4575")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    from crawler_core.settings import get_settings
    from crawler_core.vision_llm import parse_vision_llm_records
    rows = parse_vision_llm_records(page_rule, html, final_url, get_settings().browser_timeout_seconds)
    for row in rows:
        row.detail_url = ""
    if not rows:
        raise RuntimeError("领导图片未提取到有效领导记录")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
