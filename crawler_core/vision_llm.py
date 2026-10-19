from __future__ import annotations

from datetime import datetime
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawler_core.deepseek_vision import DeepSeekVisionResult, call_deepseek_vision_json
from crawler_core.llm_text import compact_text, normalize_model_order, resolve_prompt_path
from crawler_core.llm_vision import download_image_bytes
from crawler_core.models import PersonRecord
from crawler_core.rule_table import normalize_script_sequence


def build_vision_page_rule(
    rule_id: str,
    image_selector: str,
    instruction: str,
    fetch_mode: str = "online",
) -> dict[str, Any]:
    """构造只使用DeepSeek V4 Flash Vision的图片抽取规则。"""
    selector = str(image_selector or "").strip()
    if not selector:
        raise ValueError("图片大模型脚本必须提供已核验的图片选择器")
    normalized_fetch_mode = str(fetch_mode or "online").strip()
    return {
        "rule_id": normalize_script_sequence(rule_id),
        "configuration_status": "verified",
        "page_type": "图片视觉大模型抽取",
        "structure_group": "image_deepseek_v4_flash_vision_v1",
        "reuse_scope": "single_page",
        "load_mode": "图片承载",
        "fetch_mode": normalized_fetch_mode,
        "force_browser": normalized_fetch_mode.lower() == "online",
        "extract_mode": "vision_llm",
        "collector": "playwright_hidden",
        "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
        "leader_region_selector": selector,
        "locator_strategy": "custom_parse_page",
        "detail_strategy": {"required": False, "mode": "none"},
        "risk_flag": "DeepSeek视觉结果必须逐条回指同次响应的图片逐字转写",
        "confidence": "DeepSeek视觉转写与结构化证据已校验",
        "vision_strategy": {
            "required": True,
            "provider": "deepseek_v4_flash_vision_exp",
            "mode": "deepseek_vision_json",
            "target_image_selector": selector,
            "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
            "prompt_version": "deepseek_vision_v1",
            "instruction": str(instruction or "").strip(),
            "evidence_validation": "exact_normalized_substring",
        },
    }


def prepare_vision_image_tiles(image_bytes: bytes, tile_edge: int = 800) -> list[bytes]:
    """将图片铺白底并按阅读顺序切为重叠分块，避免超长图缩放丢字。"""
    from PIL import Image

    with Image.open(BytesIO(image_bytes)) as image:
        rgba_image = image.convert("RGBA")
        white_background = Image.new("RGBA", rgba_image.size, "#FFFFFF")
        white_background.alpha_composite(rgba_image)
        rgb_image = white_background.convert("RGB")
        tile_edge = max(800, int(tile_edge))
        overlap = 80
        if rgb_image.width <= tile_edge and rgb_image.height <= tile_edge:
            output = BytesIO()
            rgb_image.save(output, format="PNG")
            return [output.getvalue()]

        step = tile_edge - overlap
        x_positions = list(range(0, max(1, rgb_image.width - tile_edge + 1), step))
        y_positions = list(range(0, max(1, rgb_image.height - tile_edge + 1), step))
        final_x = max(0, rgb_image.width - tile_edge)
        final_y = max(0, rgb_image.height - tile_edge)
        if not x_positions or x_positions[-1] != final_x:
            x_positions.append(final_x)
        if not y_positions or y_positions[-1] != final_y:
            y_positions.append(final_y)

        tiles: list[bytes] = []
        for top in y_positions:
            for left in x_positions:
                right = min(rgb_image.width, left + tile_edge)
                bottom = min(rgb_image.height, top + tile_edge)
                tile = rgb_image.crop((left, top, right, bottom))
                output = BytesIO()
                tile.save(output, format="PNG")
                tiles.append(output.getvalue())
        return tiles


def find_target_image_urls(rule: dict[str, Any], html: str, final_url: str) -> list[str]:
    """按已核验选择器动态发现目标图片URL。"""
    strategy = rule.get("vision_strategy") if isinstance(rule.get("vision_strategy"), dict) else {}
    selector = str(strategy.get("target_image_selector") or "").strip()
    if not selector:
        raise ValueError("图片视觉抽取缺少target_image_selector")
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(rule.get("url", ""))
    urls: list[str] = []
    for node in soup.select(selector):
        src = str(node.get("src") or node.get("data-src") or node.get("data-original") or "").strip()
        if not src:
            continue
        image_url = urljoin(base_url, src)
        if image_url and image_url not in urls:
            urls.append(image_url)
    if not urls:
        raise ValueError(f"图片选择器未定位到有效图片：{selector}")
    return urls


def normalize_visual_evidence(value: object) -> str:
    """移除纯排版空白并压缩重复分隔符，用于逐字回指。"""
    text = re.sub(r"\s+", "", str(value or ""))
    return re.sub(r"([：:、，,；;])\1+", r"\1", text)


def evidence_contains_name(evidence: object, name: str) -> bool:
    """校验姓名可回指，并兼容视觉转写保留二字姓名间分隔符。"""
    normalized_evidence = normalize_visual_evidence(evidence)
    if name in normalized_evidence:
        return True
    if len(name) != 2:
        return False
    split_name_pattern = re.escape(name[0]) + r"[、，,；;：:]" + re.escape(name[1])
    return re.search(split_name_pattern, normalized_evidence) is not None


def clean_visual_duty(name: str, raw_duty: str) -> str:
    """删除职务首尾与当前姓名完全一致的重复文本及其紧邻分隔符。"""
    duty = compact_text(raw_duty)
    duty = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", duty)
    escaped_name = re.escape(name)
    duty = re.sub(rf"^{escaped_name}[\s：:、，,；;—-]*", "", duty)
    duty = re.sub(rf"[\s：:、，,；;—-]*{escaped_name}$", "", duty)
    return duty.strip()


def validate_visual_rows(
    rule: dict[str, Any],
    payload: dict[str, Any],
    transcription: str,
    duty_context_transcription: str,
    image_order_offset: int,
    selector: str,
) -> list[PersonRecord]:
    """验证DeepSeek抽取结果能够回指同次响应的图片逐字转写。"""
    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list):
        raise RuntimeError("DeepSeek视觉JSON缺少rows数组")
    normalized_transcription = normalize_visual_evidence(transcription)
    normalized_duty_context = normalize_visual_evidence(duty_context_transcription)
    strategy = rule.get("vision_strategy") if isinstance(rule.get("vision_strategy"), dict) else {}
    allow_group_title_context = bool(strategy.get("allow_group_title_context"))
    sequence = normalize_script_sequence(rule.get("rule_id") or rule.get("sequence"))
    pending_rows: list[tuple[int, PersonRecord]] = []
    seen_names: set[str] = set()
    for index, item in enumerate(raw_rows, start=1):
        if not isinstance(item, dict):
            continue
        name = compact_text(item.get("name")).replace(" ", "")
        raw_duty = clean_visual_duty(
            name,
            compact_text(item.get("raw_duty") or item.get("duty")),
        )
        evidence = compact_text(item.get("evidence"))
        visual_span = compact_text(item.get("visual_span")) or evidence
        if not re.fullmatch(r"[\u3400-\u9fff·•]{2,12}", name):
            continue
        if not raw_duty or not evidence or name in seen_names:
            continue
        name_in_evidence = evidence_contains_name(evidence, name)
        name_in_transcription = evidence_contains_name(transcription, name)
        if not name_in_evidence and not name_in_transcription:
            continue
        normalized_duty = normalize_visual_evidence(raw_duty)
        duty_in_evidence = normalized_duty in normalize_visual_evidence(evidence)
        duty_in_context = normalized_duty in normalized_duty_context
        if not duty_in_evidence and not (allow_group_title_context and duty_in_context):
            continue
        normalized_evidence = normalize_visual_evidence(evidence)
        normalized_span = normalize_visual_evidence(visual_span)
        duty_in_transcription = normalized_duty in normalized_transcription
        if (
            normalized_evidence not in normalized_transcription
            and normalized_span not in normalized_transcription
            and not duty_in_transcription
        ):
            continue
        seen_names.add(name)
        local_order = normalize_model_order(item.get("source_order"), index)
        order = image_order_offset + local_order
        record = PersonRecord(
            organization=str(rule.get("organization", "")),
            url=str(rule.get("url", "")),
            name=name,
            duty=raw_duty,
            detail_url="",
            evidence=raw_duty,
            confidence=str(item.get("confidence") or rule.get("confidence") or "DeepSeek视觉证据已校验"),
            parser=str(rule.get("parser", "DEEPSEEK_V4_FLASH_VISION_V1")),
            selector_summary=f"strategy=deepseek_vision；image={selector}；evidence=视觉转写回指",
            order=str(order),
            script_sequence=sequence,
        )
        record.visual_evidence = evidence
        pending_rows.append((order, record))
    pending_rows.sort(key=lambda pair: pair[0])
    return [row for _, row in pending_rows]


def write_vision_audit(
    project_dir: Path,
    rule: dict[str, Any],
    result: DeepSeekVisionResult,
    prompt_path: Path,
    image_url: str,
    image_hash: str,
    tile_count: int,
    tile_total: int,
    batch_index: int,
    batch_count: int,
    transcription: str,
    accepted_count: int,
) -> Path:
    """写出不含密钥的DeepSeek视觉调用审计JSON。"""
    sequence = normalize_script_sequence(rule.get("rule_id") or rule.get("sequence")) or "unknown"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    audit_path = (
        project_dir / "workspace" / "reports" / "llm_audit" / f"{sequence}_vision_{timestamp}.json"
    )
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "script_sequence": sequence,
        "type": "deepseek_v4_flash_vision",
        "provider": "deepseek",
        "model": result.model,
        "base_url": result.base_url,
        "prompt_path": str(prompt_path.relative_to(project_dir)),
        "prompt_hash": result.prompt_hash,
        "input_hash": result.input_hash,
        "image_url": image_url,
        "image_hash": image_hash,
        "image_preprocessing": "alpha_composite_white_rgb_png_tiles_800_overlap_80",
        "tile_count": tile_count,
        "tile_total": tile_total,
        "batch_index": batch_index,
        "batch_count": batch_count,
        "transcription": transcription,
        "accepted_count": accepted_count,
        "elapsed_seconds": round(result.elapsed_seconds, 3),
        "usage": {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
        },
        "raw_response": result.raw_text,
        "parsed_payload": result.payload,
    }
    audit_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit_path


def parse_vision_llm_records(
    rule: dict[str, Any],
    html: str,
    final_url: str,
    timeout_seconds: int,
) -> list[PersonRecord]:
    """仅使用DeepSeek视觉模型识别图片并输出经证据回指的人物记录。"""
    project_dir = Path(__file__).resolve().parents[1]
    strategy = rule.get("vision_strategy") if isinstance(rule.get("vision_strategy"), dict) else {}
    prompt_path = resolve_prompt_path(project_dir, strategy.get("prompt_path"))
    prompt_template = prompt_path.read_text(encoding="utf-8")
    image_urls = find_target_image_urls(rule, html, final_url)
    selector = str(strategy.get("target_image_selector") or "")
    vision_timeout_seconds = max(
        int(strategy.get("timeout_seconds") or 0),
        int(timeout_seconds),
        180,
    )
    rows: list[PersonRecord] = []
    seen_names: set[str] = set()
    for image_index, image_url in enumerate(image_urls, start=1):
        image_bytes, _ = download_image_bytes(
            image_url,
            final_url or str(rule.get("url", "")),
            vision_timeout_seconds,
        )
        tile_edge = int(strategy.get("tile_edge") or 800)
        prepared_image_tiles = prepare_vision_image_tiles(image_bytes, tile_edge=tile_edge)
        base_prompt = (
            f"{prompt_template}\n\n机构：{compact_text(rule.get('organization'))}"
            f"\n依据链接：{compact_text(rule.get('url') or final_url)}"
            f"\n图片序号：{image_index}\n图片URL：{image_url}"
        )
        extra_instruction = compact_text(strategy.get("instruction"))
        if extra_instruction:
            base_prompt = f"{base_prompt}\n本页补充要求：{extra_instruction}"
        tile_batch_size = max(1, int(strategy.get("tile_batch_size") or 8))
        tile_batches = [
            prepared_image_tiles[index : index + tile_batch_size]
            for index in range(0, len(prepared_image_tiles), tile_batch_size)
        ]
        image_transcriptions: list[str] = []
        for batch_index, tile_batch in enumerate(tile_batches, start=1):
            tile_start = (batch_index - 1) * tile_batch_size + 1
            tile_end = tile_start + len(tile_batch) - 1
            prompt = (
                f"{base_prompt}\n当前为全图第{tile_start}至{tile_end}块，"
                f"全图共{len(prepared_image_tiles)}块；只处理当前批次实际可见内容。"
            )
            result = call_deepseek_vision_json(
                images=[(tile, "image/png") for tile in tile_batch],
                prompt=prompt,
                project_dir=project_dir,
                timeout_seconds=vision_timeout_seconds,
            )
            transcription = str(result.payload.get("transcription") or "").strip()
            if not transcription:
                raise RuntimeError("DeepSeek视觉JSON缺少transcription逐字转写")
            image_transcriptions.append(transcription)
            batch_rows = validate_visual_rows(
                rule,
                result.payload,
                transcription,
                "\n".join(image_transcriptions),
                image_order_offset=(image_index - 1) * 10000 + (batch_index - 1) * 1000,
                selector=selector,
            )
            accepted_rows: list[PersonRecord] = []
            for row in batch_rows:
                if row.name in seen_names:
                    continue
                seen_names.add(row.name)
                accepted_rows.append(row)
            write_vision_audit(
                project_dir,
                rule,
                result,
                prompt_path,
                image_url,
                hashlib.sha256(image_bytes).hexdigest(),
                len(tile_batch),
                len(prepared_image_tiles),
                batch_index,
                len(tile_batches),
                transcription,
                len(accepted_rows),
            )
            if result.payload.get("json_recovered"):
                raise RuntimeError(
                    "DeepSeek视觉批次JSON不完整："
                    f"图片{image_index}，批次{batch_index}/{len(tile_batches)}"
                )
            rows.extend(accepted_rows)
    rows.sort(key=lambda row: int(row.order or 0))
    for index, row in enumerate(rows, start=1):
        row.order = str(index)
    return rows
