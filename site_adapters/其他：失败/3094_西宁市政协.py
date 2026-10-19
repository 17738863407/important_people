from __future__ import annotations

import hashlib
import json
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3094",
    "page_type": "图片视觉大模型抽取",
    "structure_group": "image_deepseek_v4_flash_vision_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "requests",
    "extract_mode": "vision_llm",
    "collector": "api_json",
    "parser": "DEEPSEEK_V4_FLASH_VISION_V1",
    "leader_region_selector": "img[src]",
    "api_endpoint": "https://api.xnszx.gov.cn/api/news/details",
    "risk_flag": "委员长图跨栏；DeepSeek视觉结果必须逐条回指同次响应的图片转写",
    "confidence": "DeepSeek视觉转写与结构化证据已校验",
    "filter_policy": "strong_no_wordlist",
    "vision_strategy": {
        "required": True,
        "provider": "deepseek_v4_flash_vision_exp",
        "mode": "deepseek_vision_json",
        "target_image_selector": "img[src]",
        "prompt_path": "workspace/prompts/DeepSeek视觉人物抽取_v1.txt",
        "prompt_version": "deepseek_vision_v1",
        "instruction": (
            "抽取委员名单图片中明确出现的全部姓名，按图片阅读顺序输出；"
            "只有图片本身明确表明这是委员名单时，才把raw_duty写为委员。"
        ),
        "allow_group_title_context": True,
        "evidence_validation": "exact_normalized_substring",
    },
}


def prepare_member_roster_tiles(image_bytes: bytes) -> list[bytes]:
    """在文字行之间切分委员长图，避免固定坐标截断一整行姓名。"""
    from PIL import Image

    with Image.open(BytesIO(image_bytes)) as image:
        rgba_image = image.convert("RGBA")
        white_background = Image.new("RGBA", rgba_image.size, "#FFFFFF")
        white_background.alpha_composite(rgba_image)
        rgb_image = white_background.convert("RGB")
        gray_bytes = rgb_image.convert("L").tobytes()
        width, height = rgb_image.size
        row_ink_counts = [
            sum(value < 180 for value in gray_bytes[y * width : (y + 1) * width])
            for y in range(height)
        ]
        boundaries = [0]
        target_height = 900
        while boundaries[-1] + target_height < height:
            target = boundaries[-1] + target_height
            search_start = max(boundaries[-1] + 650, target - 120)
            search_end = min(height - 1, target + 120)
            boundary = min(
                range(search_start, search_end + 1),
                key=lambda y: (sum(row_ink_counts[max(0, y - 4) : y + 5]), abs(y - target)),
            )
            boundaries.append(boundary)
        boundaries.append(height)
        tiles: list[bytes] = []
        for top, bottom in zip(boundaries, boundaries[1:]):
            crop = rgb_image.crop((0, top, rgb_image.width, bottom))
            enlarged = crop.resize(
                (round(crop.width * 1.5), round(crop.height * 1.5)),
                Image.Resampling.LANCZOS,
            )
            output = BytesIO()
            enlarged.save(output, format="PNG")
            tiles.append(output.getvalue())
        return tiles


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """从当前API动态取得委员图片并运行DeepSeek视觉解析。"""
    del html
    from crawler_core.deepseek_vision import call_deepseek_vision_json
    from crawler_core.llm_text import compact_text, resolve_prompt_path
    from crawler_core.llm_vision import download_image_bytes
    from crawler_core.settings import get_settings
    from crawler_core.vision_llm import validate_visual_rows, write_vision_audit

    detail_ids = parse_qs(urlparse(final_url).query).get("detail_id", [])
    if not detail_ids or not detail_ids[0].isdigit():
        raise RuntimeError("入口链接缺少有效detail_id，无法请求委员名录API")
    response = requests.post(
        str(page_rule.get("api_endpoint") or ""),
        data={"id": detail_ids[0]},
        headers={"Origin": "https://www.xnszx.gov.cn", "Referer": "https://www.xnszx.gov.cn/"},
        timeout=60,
        verify=False,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    content = str(data.get("content") or "") if isinstance(data, dict) else ""
    title = str(data.get("name") or "") if isinstance(data, dict) else ""
    images = BeautifulSoup(content, "html.parser").select("img[src]")
    if "委员名单" not in title or len(images) != 1:
        raise RuntimeError("委员名录API未返回可验证的委员名单图片")
    image_url = urljoin(str(page_rule.get("api_endpoint") or final_url), str(images[0].get("src") or ""))
    image_url = image_url.replace("http://api.xnszx.gov.cn", "https://api.xnszx.gov.cn")
    timeout_seconds = max(get_settings().browser_timeout_seconds, 300)
    image_bytes, _ = download_image_bytes(image_url, final_url, timeout_seconds)
    image_tiles = prepare_member_roster_tiles(image_bytes)
    project_dir = resolve_project_dir()
    strategy = page_rule["vision_strategy"]
    if not isinstance(strategy, dict):
        raise RuntimeError("3094视觉规则缺少vision_strategy字典")
    prompt_path = resolve_prompt_path(project_dir, strategy.get("prompt_path"))
    prompt_template = prompt_path.read_text(encoding="utf-8")
    records: list[object] = []
    seen_names: set[str] = set()
    transcriptions: list[str] = []
    for tile_index, tile in enumerate(image_tiles, start=1):
        prompt = (
            f"{prompt_template}\n\n机构：{compact_text(page_rule.get('organization'))}\n"
            f"依据链接：{compact_text(page_rule.get('url') or final_url)}\n"
            f"本页补充要求：{compact_text(strategy.get('instruction'))}\n"
            f"当前为同一委员名单长图第{tile_index}/{len(image_tiles)}个纵向分段，"
            "分段保留了完整横向名单行；只输出当前分段中完整可辨的姓名，边缘截断姓名不输出，"
            "重叠区域人物也只按当前可见文字正常转写。"
        )
        result = call_deepseek_vision_json(
            images=[(tile, "image/png")],
            prompt=prompt,
            project_dir=project_dir,
            timeout_seconds=timeout_seconds,
        )
        transcription = str(result.payload.get("transcription") or "").strip()
        if not transcription:
            raise RuntimeError(f"DeepSeek视觉JSON缺少逐字转写：分段{tile_index}")
        transcriptions.append(transcription)
        tile_records = validate_visual_rows(
            page_rule,
            result.payload,
            transcription,
            "\n".join(transcriptions),
            image_order_offset=(tile_index - 1) * 1000,
            selector="委员长图完整横向分段",
        )
        accepted_records = []
        for record in tile_records:
            if record.name in seen_names:
                continue
            seen_names.add(record.name)
            accepted_records.append(record)
        audit_path = write_vision_audit(
            project_dir,
            page_rule,
            result,
            prompt_path,
            image_url,
            hashlib.sha256(image_bytes).hexdigest(),
            1,
            len(image_tiles),
            tile_index,
            len(image_tiles),
            transcription,
            len(accepted_records),
        )
        audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
        audit_payload["image_preprocessing"] = "full_width_text_gap_tiles_about_900_lanczos_1_5x"
        audit_path.write_text(
            json.dumps(audit_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if result.payload.get("json_recovered"):
            raise RuntimeError(f"DeepSeek视觉JSON不完整：分段{tile_index}")
        records.extend(accepted_records)
    records.sort(key=lambda record: int(record.order or 0))
    for index, record in enumerate(records, start=1):
        record.order = str(index)
    transcription_text = "".join(transcriptions).replace(" ", "")
    declared_count = __import__("re").search(r"共(\d+)名", transcription_text)
    if declared_count is None:
        raise RuntimeError("委员名单未识别到总人数声明")
    expected_count = int(declared_count.group(1))
    if len(records) != expected_count:
        raise RuntimeError(f"委员完整性校验失败：图片声明{expected_count}名，接受{len(records)}名")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
