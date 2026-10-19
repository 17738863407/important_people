from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "3475",
    "configuration_status": "verified",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "image_deepseek_v4_flash_vision_v1",
    "reuse_scope": "single_page",
    "load_mode": "图片承载",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "vision_llm",
    "collector": "auto",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": ".ldtd-con.gsld-con > li > img[src]",
    "name_selector": "DeepSeek视觉提取",
    "duty_selector": "DeepSeek视觉提取原始职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".ldtd-con.gsld-con > li > img[src]"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导信息由单张图片承载，DeepSeek视觉结果必须逐条回指同次响应的图片转写",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "filter_policy": "weak_allow_wordlist",
    "locator_strategy": "custom_parse_page",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": ".ldtd-con.gsld-con > li > img[src]",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": "按图片原始版面从上到下、从左到右抽取公司现任领导姓名及对应职务；图片每一排均由若干独立人物卡片组成，图片转写可能先连续输出同排姓名，再把同排各人的职务合并到一行。必须按卡片位置把合并职务拆成与姓名数量相同、顺序一致的一一对应raw_duty，不得把含有多个相邻卡片职务的合并串重复分配给多人。合并职务中若连续出现两个“党组成员”，它们分别属于左右相邻的两张人物卡片：前一个保留在前一职务末尾，后一个保留在后一职务开头，不得把两个“党组成员”都归入同一人物。证据字段有硬性格式：同一排所有人物的evidence必须逐字使用完全相同的连续图片转写原文块，即从该排第一个姓名开始，依次包含该排全部姓名和全部职务，直到该排最后一个职务结束；visual_span也必须逐字使用对应的完整连续原文。禁止为单个人拼接不相邻的姓名行和职务片段。不推断、不补写，不把页面导航和装饰文字作为人物。",
        "evidence_validation": "exact_normalized_substring",
    },
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """调用DeepSeek视觉模型解析图片并校验证据。"""
    from collections import Counter, defaultdict

    from crawler_core.vision_llm import parse_vision_llm_records
    from crawler_core.settings import get_settings

    records = parse_vision_llm_records(
        rule=page_rule,
        html=html,
        final_url=final_url,
        timeout_seconds=get_settings().browser_timeout_seconds,
    )
    records_by_evidence: dict[str, list[object]] = defaultdict(list)
    for record in records:
        normalized_evidence = "".join(str(getattr(record, "visual_evidence", "")).split())
        records_by_evidence[normalized_evidence].append(record)
    for evidence, grouped_records in records_by_evidence.items():
        assigned_counts = Counter("".join(record.duty.split()) for record in grouped_records)
        for duty, assigned_count in assigned_counts.items():
            if assigned_count > evidence.count(duty):
                raise ValueError("图片连续证据块无法证明多人职务的一一对应关系")
    return records

def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
