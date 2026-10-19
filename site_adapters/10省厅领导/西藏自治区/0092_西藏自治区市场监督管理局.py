from __future__ import annotations

import base64
import hashlib
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0092",
    "configuration_status": "verified",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "image_deepseek_v4_flash_vision_v1",
    "reuse_scope": "single_page",
    "load_mode": "图片承载",
    "fetch_mode": "raw_http",
    "extract_mode": "vision_llm",
    "collector": "static_http",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": "div.protection_contentR div.contents img[src]",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": ["div.protection_contentR div.contents img[src]"],
        "exclude_selectors": [],
    },
    "locator_strategy": "custom_parse_page",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "领导名单完全承载在正文图片中；DeepSeek视觉结果必须逐条回指同次响应的图片逐字转写",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": "div.protection_contentR div.contents img[src]",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": (
            "只抽取目标领导名单图片中明确出现的当前人物姓名及其职务，严格按图片从上到下顺序输出。"
            "当前版面为姓名行与其后一行职务一一相邻的结构；每个姓名只能绑定紧随其后的职务行。"
            "保持图片中可确认的原始职务，不扩写机构简称，不依据历史结果或常识补全任何字段。"
        ),
        "evidence_validation": "exact_normalized_substring",
    },
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """运行DeepSeek V4 Flash视觉抽取和证据解析。"""
    from crawler_core.settings import get_settings
    import crawler_core.vision_llm as vision_llm

    soup = BeautifulSoup(html or "", "html.parser")
    selector = page_rule["vision_strategy"]["target_image_selector"]
    inline_images: dict[str, tuple[bytes, str]] = {}
    for image in soup.select(selector):
        source = str(image.get("src") or "").strip()
        if not source.startswith("data:image/"):
            continue
        header, separator, payload = source.partition(",")
        if not separator or ";base64" not in header:
            raise RuntimeError("目标内嵌图片不是base64数据")
        content_type = header[5:].split(";", 1)[0].lower()
        if content_type not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
            raise RuntimeError(f"目标内嵌图片类型不受支持：{content_type}")
        image_bytes = base64.b64decode(payload, validate=True)
        image_key = f"inline-image://{hashlib.sha256(image_bytes).hexdigest()}"
        inline_images[image_key] = (image_bytes, content_type)
        image["src"] = image_key

    original_downloader = vision_llm.download_image_bytes

    def download_current_image(
        image_url: str, page_url: str, timeout_seconds: int
    ) -> tuple[bytes, str]:
        if image_url in inline_images:
            return inline_images[image_url]
        return original_downloader(image_url, page_url, timeout_seconds)

    vision_llm.download_image_bytes = download_current_image
    try:
        return vision_llm.parse_vision_llm_records(
            page_rule,
            str(soup),
            final_url,
            get_settings().browser_timeout_seconds,
        )
    finally:
        vision_llm.download_image_bytes = original_downloader


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
