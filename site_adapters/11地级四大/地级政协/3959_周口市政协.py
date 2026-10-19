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
    """构造周口市政协四张领导班子图片的 DeepSeek 视觉抽取规则。"""
    from crawler_core.vision_llm import build_vision_page_rule

    return build_vision_page_rule(
        rule_id=rule_id,
        image_selector="#Zoom > p > img[src*='zimg.hnzx.gov.cn']",
        instruction=(
            "四张图片共同组成中国人民政治协商会议第五届周口市委员会当前领导班子成员页面。"
            "只抽取图片中明确出现的姓名和与其同一人物区域对应的完整现任职务，"
            "严格按第一至第四张图片以及各图自上而下、从左到右的阅读顺序输出；"
            "不得把页面标题、照片文件名、分工、简历或装饰文字识别为人物，不得推断或补全。"
        ),
        fetch_mode="raw_http",
    )


def clean_evidence(value: str, name: str) -> str:
    """仅删除证据首尾与当前姓名完全一致的重复姓名及紧邻分隔符。"""
    text = str(value or "").strip()
    exact_name = str(name or "").strip()
    if not text or not exact_name:
        return text
    text = re.sub(rf"^{re.escape(exact_name)}[：:、,，\-—\s]*", "", text, count=1).strip()
    text = re.sub(rf"[：:、,，\-—\s]*{re.escape(exact_name)}$", "", text, count=1).strip()
    return re.sub(r"；+", "；", re.sub(r"\s+", "；", text)).strip("；")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """执行 DeepSeek 视觉转写、结构化抽取和证据回指。"""
    from crawler_core.vision_llm import parse_vision_llm_records
    from crawler_core.settings import get_settings

    rows = parse_vision_llm_records(
        page_rule,
        html,
        final_url,
        max(get_settings().browser_timeout_seconds, 180),
    )
    for row in rows:
        evidence = clean_evidence(str(row.evidence or row.duty or ""), str(row.name or ""))
        row.duty = evidence
        row.evidence = evidence
    return rows


def main(rule_id: str) -> None:
    """运行当前图片页面脚本，且不写公共采集方式成功记录。"""
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
    print(f"尝试链路：{runtime_context.get('attempted_collectors', [])}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3959"
    main(rule_id_value)
