from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2561",
    "configuration_status": "verified",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "image_deepseek_v4_flash_vision_v1",
    "reuse_scope": "single_page",
    "load_mode": "图片承载",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "vision_llm",
    "collector": "playwright_hidden",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": "div#nsks img[src]",
    "content_path": "/njshjbhj/xxgkzl/jggk/index_17447.html",
    "locator_strategy": "custom_parse_page",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口通过脚本加载机构概况页，领导信息仅由当前图片承载",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": "div#nsks img[src]",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": "只抽取领导信息图片中明确出现的姓名与当前职务，保持图片阅读顺序，忽略标题和装饰文字。",
        "evidence_validation": "exact_normalized_substring",
    },
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """动态发现机构概况内页，再运行DeepSeek视觉证据解析通道。"""
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.vision_llm import parse_vision_llm_records
    from crawler_core.settings import get_settings

    soup = BeautifulSoup(html, "html.parser")
    link = soup.select_one("a#c_215[href]")
    href = str(link.get("href") or "").strip() if link else ""
    match = re.search(
        r'jQuery\("#xxgk_215 a"\)\.attr\("href","([^"]+)"\)',
        html,
    )
    if match:
        href = match.group(1)
    if not href:
        href = str(page_rule.get("content_path") or "").strip()
    if not href:
        raise RuntimeError("入口页未发现概况信息内页地址")
    inner_url = urljoin(final_url, href)
    timeout = get_settings().browser_timeout_seconds
    inner_result = fetch_html_with_strategy(inner_url, strategy="raw_http", timeout=timeout)
    return parse_vision_llm_records(
        page_rule,
        inner_result.html,
        inner_result.final_url,
        timeout,
    )


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
