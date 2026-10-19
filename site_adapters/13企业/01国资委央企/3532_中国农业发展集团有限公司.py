from __future__ import annotations

import sys
import queue
import threading
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3532",
    "configuration_status": "verified",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "image_deepseek_v4_flash_vision_v1",
    "reuse_scope": "single_page",
    "load_mode": "图片承载",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "vision_llm",
    "collector": "playwright_hidden",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": ".main_box_r img[src]",
    "locator_strategy": "custom_parse_page",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "独立HTTP会话返回458，必须在当前浏览器会话内动态下载图片",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": ".main_box_r img[src]",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": (
            "目标图片是党委会领导信息。严格按图片版面从上到下、从左到右的原始顺序，"
            "只抽取每个人物区域中明确显示的姓名和现任职务；不抽取栏目标题、单位介绍或分工。"
            "每条evidence和visual_span必须包含该人物姓名及其对应职务的连续图片转写原文。"
        ),
        "evidence_validation": "exact_normalized_substring",
    },
}


def _download_image_in_browser(image_url: str, page_url: str, timeout_seconds: int) -> tuple[bytes, str]:
    """复用浏览器会话取得受安全检查保护的当前图片。"""
    result_queue: queue.Queue[tuple[bytes, str] | BaseException] = queue.Queue(maxsize=1)

    def worker() -> None:
        from playwright.sync_api import sync_playwright

        timeout_ms = max(1, timeout_seconds) * 1000
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    context = browser.new_context()
                    page = context.new_page()
                    page.goto(page_url, wait_until="networkidle", timeout=timeout_ms)
                    image = page.locator(".main_box_r img[src]")
                    if image.count() != 1:
                        raise RuntimeError(f"党委会目标图片数量异常：{image.count()}")
                    image.wait_for(state="visible", timeout=timeout_ms)
                    current_src = str(image.evaluate("node => node.currentSrc || node.src") or "")
                    if urljoin(page_url, current_src) != image_url:
                        raise RuntimeError("浏览器当前图片与HTML动态发现图片不一致")
                    response = context.request.get(
                        image_url,
                        headers={"Referer": page_url},
                        timeout=timeout_ms,
                    )
                    if not response.ok:
                        raise RuntimeError(f"浏览器会话下载图片失败：HTTP {response.status}")
                    content_type = str(response.headers.get("content-type") or "image/png").split(";", 1)[0]
                    if not content_type.startswith("image/"):
                        raise RuntimeError(f"浏览器目标资源不是图片：{content_type}")
                    result_queue.put((response.body(), content_type))
                finally:
                    browser.close()
        except BaseException as error:
            result_queue.put(error)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=max(1, timeout_seconds) + 15)
    if thread.is_alive():
        raise TimeoutError("浏览器会话下载党委会图片超时")
    result = result_queue.get_nowait()
    if isinstance(result, BaseException):
        raise result
    return result


def parse_page(html: str, final_url: str, page_rule: dict[str, object]):
    """对浏览器动态发现的党委会图片执行DeepSeek视觉证据校验。"""
    from crawler_core import vision_llm
    from crawler_core.settings import get_settings

    original_downloader = vision_llm.download_image_bytes
    vision_llm.download_image_bytes = _download_image_in_browser
    try:
        return vision_llm.parse_vision_llm_records(
            page_rule,
            html,
            final_url,
            get_settings().browser_timeout_seconds,
        )
    finally:
        vision_llm.download_image_bytes = original_downloader


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
