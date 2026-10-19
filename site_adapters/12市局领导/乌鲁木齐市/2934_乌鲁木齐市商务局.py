from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "2934",
    "configuration_status": "verified",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "image_deepseek_v4_flash_vision_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "vision_llm",
    "collector": "auto",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": "#NewsContent .gjnr",
    "name_selector": "DeepSeek视觉提取",
    "duty_selector": "DeepSeek视觉提取原始职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["#NewsContent .gjnr"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "新页面头像不含姓名文字，须截取可见领导正文后由DeepSeek视觉解析",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "filter_policy": "weak_allow_wordlist",
    "locator_strategy": "custom_parse_page",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": "#NewsContent .gjnr",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": "输入是官方页面领导正文的可见截图；按页面从上到下只抽取每位领导介绍首句中的姓名和现任职务，不把后续分管、负责、联系内容写成职务。",
        "evidence_validation": "exact_normalized_substring",
    },
}


def capture_leader_content_screenshot(
    project_dir: Path,
    url: str,
    timeout_seconds: int,
) -> tuple[bytes, int]:
    """在独立general Python进程中截取领导正文，避免同步Playwright与事件循环冲突。"""
    helper_code = r"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from crawler_core.fetcher import get_playwright_launch_args

url, output_path, timeout_text = sys.argv[1:4]
timeout_ms = int(timeout_text) * 1000
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, args=get_playwright_launch_args())
    try:
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        content = page.locator("#NewsContent .gjnr")
        content.wait_for(state="visible", timeout=timeout_ms)
        expected_count = content.locator("p > img[src*='/images/']").count()
        content.screenshot(path=output_path, type="png")
        print(expected_count)
    finally:
        browser.close()
"""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        screenshot_path = Path(temp_file.name)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                helper_code,
                url,
                str(screenshot_path),
                str(timeout_seconds),
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds + 30,
            check=False,
        )
        if completed.returncode != 0:
            error_text = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(f"2934领导正文截图失败：{error_text}")
        expected_count = int(completed.stdout.strip().splitlines()[-1])
        return screenshot_path.read_bytes(), expected_count
    finally:
        screenshot_path.unlink(missing_ok=True)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """截取可见领导正文，调用DeepSeek视觉模型解析并校验证据。"""
    from crawler_core.deepseek_vision import call_deepseek_vision_json
    from crawler_core.llm_text import compact_text, resolve_prompt_path
    from crawler_core.settings import get_settings
    from crawler_core.vision_llm import (
        prepare_vision_image_tiles,
        validate_visual_rows,
        write_vision_audit,
    )

    project_dir = resolve_project_dir()
    strategy = page_rule["vision_strategy"]
    if not isinstance(strategy, dict):
        raise RuntimeError("2934视觉规则缺少vision_strategy字典")
    timeout_seconds = max(get_settings().browser_timeout_seconds, 180)
    screenshot_bytes, expected_count = capture_leader_content_screenshot(
        project_dir,
        str(page_rule.get("url") or final_url),
        timeout_seconds,
    )
    if expected_count <= 0:
        raise RuntimeError("2934可见领导正文未定位到人物头像")

    prompt_path = resolve_prompt_path(project_dir, strategy.get("prompt_path"))
    prompt_template = prompt_path.read_text(encoding="utf-8")
    image_tiles = prepare_vision_image_tiles(screenshot_bytes)
    tile_batch_size = 8
    tile_batches = [
        image_tiles[index : index + tile_batch_size]
        for index in range(0, len(image_tiles), tile_batch_size)
    ]
    records: list[object] = []
    seen_names: set[str] = set()
    transcriptions: list[str] = []
    for batch_index, tile_batch in enumerate(tile_batches, start=1):
        tile_start = (batch_index - 1) * tile_batch_size + 1
        tile_end = tile_start + len(tile_batch) - 1
        prompt = (
            f"{prompt_template}\n\n机构：{compact_text(page_rule.get('organization'))}\n"
            f"依据链接：{compact_text(page_rule.get('url') or final_url)}\n"
            f"本页补充要求：{compact_text(strategy.get('instruction'))}\n"
            f"当前为领导正文截图第{tile_start}至{tile_end}块，共{len(image_tiles)}块；"
            "截图中的人物头像只用于划分人物区域，姓名与职务必须来自头像后的可见介绍首句。"
        )
        result = call_deepseek_vision_json(
            images=[(image, "image/png") for image in tile_batch],
            prompt=prompt,
            project_dir=project_dir,
            timeout_seconds=timeout_seconds,
        )
        transcription = str(result.payload.get("transcription") or "").strip()
        if not transcription:
            raise RuntimeError(f"DeepSeek视觉JSON缺少逐字转写：批次{batch_index}")
        transcriptions.append(transcription)
        batch_records = validate_visual_rows(
            page_rule,
            result.payload,
            transcription,
            "\n".join(transcriptions),
            image_order_offset=(batch_index - 1) * 1000,
            selector="#NewsContent .gjnr截图",
        )
        accepted_records = []
        for record in batch_records:
            if record.name in seen_names:
                continue
            seen_names.add(record.name)
            accepted_records.append(record)
        write_vision_audit(
            project_dir,
            page_rule,
            result,
            prompt_path,
            f"{final_url}#NewsContent.gjnr",
            hashlib.sha256(screenshot_bytes).hexdigest(),
            len(tile_batch),
            len(image_tiles),
            batch_index,
            len(tile_batches),
            transcription,
            len(accepted_records),
        )
        if result.payload.get("json_recovered"):
            raise RuntimeError(f"DeepSeek视觉JSON不完整：批次{batch_index}")
        records.extend(accepted_records)
    records.sort(key=lambda record: int(record.order or 0))
    for index, record in enumerate(records, start=1):
        record.order = str(index)
    if len(records) != expected_count:
        raise RuntimeError(f"领导完整性校验失败：头像{expected_count}张，接受{len(records)}人")
    for record in records:
        visual_evidence = str(getattr(record, "visual_evidence", ""))
        first_part, separator, _ = visual_evidence.partition("。")
        first_evidence = first_part.strip() + ("。" if separator else "")
        normalized_evidence = "".join(first_evidence.split())
        normalized_name = "".join(record.name.split())
        normalized_duty = "".join(record.duty.rstrip("。").split())
        if normalized_name not in normalized_evidence or normalized_duty not in normalized_evidence:
            raise ValueError(f"图片职务证据首句无法回指：{record.name}")
        if any(noise in first_evidence for noise in ("主持", "负责", "分管", "联系")):
            raise ValueError(f"图片职务证据首句混入职责分工：{record.name}")
        record.evidence = record.duty
    return records


def main() -> None:
    """运行当前DeepSeek图片视觉解析脚本。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
