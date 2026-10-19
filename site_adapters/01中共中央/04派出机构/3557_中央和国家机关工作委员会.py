from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造旗帜网工委领导图片的 DeepSeek 视觉抽取规则。"""
    from crawler_core.vision_llm import build_vision_page_rule

    return build_vision_page_rule(
        rule_id=rule_id,
        image_selector='.flag-text-con > p > img[src*="/NMediaFile/"]',
        instruction=(
            "只抽取标题‘中央和国家机关工委领导’下方名单图片中明确列出的现任人员；"
            "姓名位于每行左侧，依据说明取同一行右侧的完整现任职务文字，"
            "跨行延续的职务必须与上一姓名合并；严格按照图片自上而下的原始顺序输出。"
            "不得把图片标题、机构名或职务中的文字识别为姓名，不得根据常识补全。"
        ),
        fetch_mode="raw_http",
    )


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """执行 DeepSeek 视觉转写、结构化抽取及证据校验。"""
    from crawler_core.vision_llm import parse_vision_llm_records
    from crawler_core.settings import get_settings

    rows = parse_vision_llm_records(
        page_rule,
        html,
        final_url,
        max(get_settings().browser_timeout_seconds, 180),
    )
    for row in rows:
        name = str(row.name or "").strip()
        evidence = str(row.evidence or row.duty or "").strip()
        if name:
            evidence = re.sub(
                rf"^{re.escape(name)}[：:、,，\-—\s]*",
                "",
                evidence,
                count=1,
            ).strip()
        row.duty = evidence
        row.evidence = evidence
    return rows


def main(rule_id: str) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        build_page_rule(rule_id),
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"执行形态：{runtime_context.get('execution_mode', '')}")
    print(f"尝试链路：{runtime_context.get('attempted_collectors', [])}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3557"
    main(rule_id_value)
