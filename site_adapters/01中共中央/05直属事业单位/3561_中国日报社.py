from __future__ import annotations

import sys
import re
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造报社编委会图片的 DeepSeek 视觉抽取规则。"""
    from crawler_core.vision_llm import build_vision_page_rule

    return build_vision_page_rule(
        rule_id=rule_id,
        image_selector='[id="2"] .Cont4 img',
        instruction=(
            "只抽取报社编委会图片中明确列出的现任人员姓名和对应职务，"
            "按图片自上而下、从左到右的阅读顺序输出；不得抽取栏目标题或推断缺失信息。"
        ),
        fetch_mode="raw_http",
    )


def remove_repeated_name_suffix(text: str, name: str) -> str:
    """删除职务末尾与当前姓名完全一致的重复姓名及紧邻分隔符。"""
    value = str(text or "").strip()
    exact_name = str(name or "").strip()
    if not value or not exact_name:
        return value
    return re.sub(rf"[：:、,，\-—\s]*{re.escape(exact_name)}$", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """执行 DeepSeek 视觉转写、结构化抽取及证据校验。"""
    from crawler_core.vision_llm import parse_vision_llm_records
    from crawler_core.settings import get_settings

    rows = parse_vision_llm_records(
        page_rule,
        html,
        final_url,
        get_settings().browser_timeout_seconds,
    )
    for row in rows:
        cleaned_evidence = remove_repeated_name_suffix(row.evidence, row.name)
        row.duty = cleaned_evidence
        row.evidence = cleaned_evidence
    return rows


def main(rule_id: str) -> None:
    """运行当前页面脚本。"""
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
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3561"
    main(rule_id_value)
