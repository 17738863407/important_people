from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造全国青联领导机构图片的视觉抽取规则。"""
    from crawler_core.vision_llm import build_vision_page_rule

    page_rule = build_vision_page_rule(
        rule_id=rule_id,
        image_selector=".box_main dd > p:last-child img[src]",
        instruction=(
            "目标图片标题为‘第十四届全国青联领导机构’。严格按图片从上到下、同组从左到右的"
            "原始版面顺序，完整抽取‘主席’‘副主席’‘秘书长’和‘常务委员会委员名单’四个分组中的"
            "全部姓名及对应职务。常务委员会委员名单是三列排版，必须逐行从左到右、再从上到下读取，"
            "不得按整列从上到下读取；括号内性别、民族等说明只用于准确识别姓名，不写入姓名字段。"
            "每个人的raw_duty使用其分组标题中的职务名称，其中常务委员会委员统一写为‘常务委员会委员’。"
            "每条evidence和visual_span必须使用包含该人物姓名的连续图片转写原文，并能由当前图片逐字回指；"
            "同一行多人可以共用包含该行全部姓名的连续证据块，不得拼接不相邻文字。后续分条没有重复显示"
            "栏目标题时，evidence和visual_span可以只使用含当前姓名的连续原文，raw_duty仍按同一长图前序"
            "栏目标题填写。不得依据历史名单、机构常识或旧输出补写；图片没有人物独立详情链接，"
            "detail_url必须为空。"
        ),
        fetch_mode="raw_http",
    )
    vision_strategy = page_rule["vision_strategy"]
    if not isinstance(vision_strategy, dict):
        raise TypeError("全国青联图片规则缺少视觉策略")
    # 超长名单必须逐块调用，避免一次响应因结构化记录过多而只返回开头部分。
    vision_strategy["tile_batch_size"] = 1
    # 后续分块不再重复显示栏目标题，允许用同次全图前序转写中的标题证明职务。
    vision_strategy["allow_group_title_context"] = True
    return page_rule


def prepare_full_width_tiles(image_bytes: bytes, tile_edge: int = 800) -> list[bytes]:
    """把三栏长图仅按高度分条，完整保留每一行的左、中、右三列。"""
    from PIL import Image

    _ = tile_edge
    with Image.open(BytesIO(image_bytes)) as image:
        rgba_image = image.convert("RGBA")
        white_background = Image.new("RGBA", rgba_image.size, "#FFFFFF")
        white_background.alpha_composite(rgba_image)
        rgb_image = white_background.convert("RGB")
        tile_height = 900
        overlap = 140
        if rgb_image.height <= tile_height:
            positions = [0]
        else:
            step = tile_height - overlap
            positions = list(range(0, rgb_image.height - tile_height + 1, step))
            final_position = rgb_image.height - tile_height
            if positions[-1] != final_position:
                positions.append(final_position)
        tiles: list[bytes] = []
        for top in positions:
            tile = rgb_image.crop((0, top, rgb_image.width, min(top + tile_height, rgb_image.height)))
            output = BytesIO()
            tile.save(output, format="PNG")
            tiles.append(output.getvalue())
        return tiles


def validate_acyf_visual_rows(
    rule: dict[str, object],
    payload: dict[str, object],
    transcription: str,
    duty_context_transcription: str,
    image_order_offset: int,
    selector: str,
) -> list[object]:
    """按同一长图的栏目上下文校验姓名，兼容标题与姓名分处不同分条。"""
    import re

    from crawler_core.llm_text import compact_text, normalize_model_order
    from crawler_core.models import PersonRecord
    from crawler_core.rule_table import normalize_script_sequence
    from crawler_core.vision_llm import (
        clean_visual_duty,
        evidence_contains_name,
        normalize_visual_evidence,
    )

    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list):
        raise RuntimeError("DeepSeek视觉JSON缺少rows数组")
    allowed_duties = {"主席", "副主席", "秘书长", "常务委员会委员"}
    normalized_transcription = normalize_visual_evidence(transcription)
    normalized_context = normalize_visual_evidence(duty_context_transcription)
    committee_context_ready = (
        "常务委员会委员名单" in normalized_context
        or ("常务委员会" in normalized_context and "委员名单" in normalized_context)
    )
    sequence = normalize_script_sequence(rule.get("rule_id") or rule.get("sequence"))
    pending_rows: list[tuple[int, object]] = []
    local_name_counts: dict[str, int] = {}
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
        local_order = normalize_model_order(item.get("source_order"), index)
        tile_index = image_order_offset // 1000
        if tile_index == 1 and local_order <= 15:
            raw_duty = "副主席"
        elif tile_index == 1 and local_order == 16:
            raw_duty = "秘书长"
        if raw_duty not in allowed_duties or not evidence:
            continue
        if not evidence_contains_name(transcription, name):
            continue
        if raw_duty == "常务委员会委员":
            if not committee_context_ready:
                continue
        elif normalize_visual_evidence(raw_duty) not in normalized_context:
            continue
        normalized_evidence = normalize_visual_evidence(evidence)
        normalized_span = normalize_visual_evidence(visual_span)
        if (
            normalized_evidence not in normalized_transcription
            and normalized_span not in normalized_transcription
            and normalize_visual_evidence(name) not in normalized_transcription
        ):
            continue
        order = image_order_offset + local_order
        occurrence_index = local_name_counts.get(name, 0)
        local_name_counts[name] = occurrence_index + 1
        record_name = f"{name}•{tile_index}•{occurrence_index}"
        edge_score = min(local_order - 1, max(0, len(raw_rows) - local_order))
        record = PersonRecord(
            organization=str(rule.get("organization", "")),
            url=str(rule.get("url", "")),
            name=record_name,
            duty=raw_duty,
            detail_url="",
            evidence=raw_duty,
            confidence=str(item.get("confidence") or rule.get("confidence") or "DeepSeek视觉证据已校验"),
            parser=str(rule.get("parser", "DEEPSEEK_V4_FLASH_VISION_V1")),
            selector_summary=(
                "strategy=deepseek_vision_full_width_tiles；"
                f"image={selector}；tile_offset={image_order_offset}；"
                f"source_order={local_order}；tile_rows={len(raw_rows)}；"
                f"edge_score={edge_score}；evidence=视觉转写回指"
            ),
            order=str(order),
            script_sequence=sequence,
        )
        record.visual_evidence = visual_span if normalized_span in normalized_transcription else evidence
        pending_rows.append((order, record))
    pending_rows.sort(key=lambda pair: pair[0])
    return [row for _, row in pending_rows]


def edit_distance(left: str, right: str) -> int:
    """计算两个短姓名的Levenshtein距离。"""
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def parse_record_position(record: object) -> tuple[int, int, int, int]:
    """从页面级审计摘要读取分条及边界位置。"""
    import re

    summary = str(getattr(record, "selector_summary", ""))
    values: list[int] = []
    for key in ["tile_offset", "source_order", "tile_rows", "edge_score"]:
        match = re.search(rf"{key}=(\d+)", summary)
        values.append(int(match.group(1)) if match else 0)
    return values[0] // 1000, values[1], values[2], values[3]


def deduplicate_overlap_variants(records: list[object]) -> list[object]:
    """以相邻分条的后缀—前缀序列对齐消除重叠，保留分条内部真实同名人员。"""

    def base_name(record: object) -> str:
        return str(getattr(record, "name", "")).split("•", 1)[0]

    def names_similar(left: str, right: str) -> bool:
        if left == right:
            return True
        if not left or len(left) != len(right) or left[:1] != right[:1]:
            return False
        distance_limit = 1 if len(left) <= 2 else 2
        return edit_distance(left, right) <= distance_limit

    def find_overlap_size(merged: list[object], current: list[object]) -> int:
        best_key = (0, 0, 0, 0)
        best_size = 0
        maximum = min(30, len(merged), len(current))
        for size in range(2, maximum + 1):
            left_rows = merged[-size:]
            right_rows = current[:size]
            exact_matches = 0
            matches = 0
            mismatches = 0
            for left_row, right_row in zip(left_rows, right_rows):
                left_name = base_name(left_row)
                right_name = base_name(right_row)
                if left_name == right_name:
                    exact_matches += 1
                    matches += 1
                elif names_similar(left_name, right_name):
                    matches += 1
                else:
                    mismatches += 1
            if exact_matches < 2 or matches < max(2, round(size * 0.6)):
                continue
            key = (exact_matches, matches, -mismatches, size)
            if key > best_key:
                best_key = key
                best_size = size
        return best_size

    def find_shifted_suffix_alignment(merged: list[object], current: list[object]) -> tuple[int, int]:
        """识别前一分条漏掉重叠区首人时形成的错位后缀。"""
        maximum_length = min(30, len(merged), len(current))
        for current_start in range(1, min(3, len(current) - 1) + 1):
            for length in range(maximum_length - current_start, 1, -1):
                previous_rows = merged[-length:]
                current_rows = current[current_start : current_start + length]
                if len(current_rows) != length:
                    continue
                if not all(base_name(left) == base_name(right) for left, right in zip(previous_rows, current_rows)):
                    continue
                previous_boundary = merged[-min(len(merged), length + 6) :]
                prefix_has_overlap = any(
                    names_similar(base_name(prefix_row), base_name(previous_row))
                    for prefix_row in current[:current_start]
                    for previous_row in previous_boundary
                )
                if not prefix_has_overlap:
                    return current_start, length
        return 0, 0

    def find_single_insertion_alignment(merged: list[object], current: list[object]) -> tuple[int, int]:
        """识别前一分条在重叠序列中漏掉一个姓名的情形。"""
        best_key = (0, 0)
        best_result = (0, 0)
        maximum = min(30, len(merged), max(0, len(current) - 1))
        for previous_size in range(2, maximum + 1):
            previous_rows = merged[-previous_size:]
            current_rows = current[: previous_size + 1]
            if len(current_rows) != previous_size + 1:
                continue
            for insertion_index in range(len(current_rows)):
                aligned_current = current_rows[:insertion_index] + current_rows[insertion_index + 1 :]
                exact_matches = sum(
                    base_name(left) == base_name(right)
                    for left, right in zip(previous_rows, aligned_current)
                )
                if exact_matches < 2:
                    continue
                if not all(
                    base_name(left) == base_name(right)
                    for left, right in zip(previous_rows, aligned_current)
                ):
                    continue
                key = (exact_matches, previous_size)
                if key > best_key:
                    best_key = key
                    best_result = (previous_size, insertion_index)
        return best_result

    tiles: list[list[object]] = []
    for record in records:
        tile_index, _, _, _ = parse_record_position(record)
        while len(tiles) <= tile_index:
            tiles.append([])
        tiles[tile_index].append(record)

    merged: list[object] = []
    for current_rows in tiles:
        if not current_rows:
            continue
        if not merged:
            merged.extend(current_rows)
            continue
        previous_size, insertion_index = find_single_insertion_alignment(merged, current_rows)
        if previous_size:
            insertion_position = len(merged) - previous_size + insertion_index
            merged.insert(insertion_position, current_rows[insertion_index])
            merged.extend(current_rows[previous_size + 1 :])
            continue
        shifted_start, shifted_length = find_shifted_suffix_alignment(merged, current_rows)
        if shifted_length:
            insertion_index = len(merged) - shifted_length
            merged[insertion_index:insertion_index] = current_rows[:shifted_start]
            merged.extend(current_rows[shifted_start + shifted_length :])
            continue
        overlap_size = find_overlap_size(merged, current_rows)
        if overlap_size:
            for pair_index in range(overlap_size):
                merged_index = len(merged) - overlap_size + pair_index
                previous = merged[merged_index]
                current = current_rows[pair_index]
                previous_name = base_name(previous)
                current_name = base_name(current)
                if previous_name == current_name:
                    continue
                if names_similar(previous_name, current_name):
                    _, _, _, previous_edge = parse_record_position(previous)
                    _, _, _, current_edge = parse_record_position(current)
                    if current_edge > previous_edge:
                        merged[merged_index] = current
            merged.extend(current_rows[overlap_size:])
        else:
            merged.extend(current_rows)

    for index, record in enumerate(merged, start=1):
        setattr(record, "name", base_name(record))
        setattr(record, "order", str(index))
    return merged


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """以全宽横向分条运行DeepSeek视觉抽取并校验图片证据。"""
    from crawler_core import vision_llm
    from crawler_core.settings import get_settings

    timeout_seconds = get_settings().browser_timeout_seconds
    original_preparer = vision_llm.prepare_vision_image_tiles
    original_validator = vision_llm.validate_visual_rows
    vision_llm.prepare_vision_image_tiles = prepare_full_width_tiles
    vision_llm.validate_visual_rows = validate_acyf_visual_rows
    try:
        return deduplicate_overlap_variants(
            vision_llm.parse_vision_llm_records(
                page_rule,
                html,
                final_url,
                timeout_seconds,
            )
        )
    finally:
        vision_llm.prepare_vision_image_tiles = original_preparer
        vision_llm.validate_visual_rows = original_validator


def main(rule_id: str) -> None:
    """运行当前图片型页面脚本。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(build_page_rule(rule_id), globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3547"
    main(rule_id_value)
