from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "2918",
    "page_type": "人物列表完整页",
    "structure_group": "nanjing_culture_tourism_image_profile_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_then_iframe_http",
    "parser": "page_nanjing_culture_tourism_image_profile_v2",
    "leader_region_selector": "iframe#dataList -> #jgcon3图片人物块",
    "name_selector": "每张人物图片后的首个非空文本段开头",
    "duty_selector": "同一首行简介内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "图片下方第一行简介结构；必须以图片为锚点且不得跨越下一张人物图片",
    "confidence": "high",
    "filter_policy": "weak_structure_wordlist_allowed",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"frame_selector": "iframe#dataList[src]", "leader_region_selector": "#jgcon3", "image_selector": "#jgcon3 p img", "row_selector": "图片后且下一图片前首个非空p"},
        "api": {"enabled": False, "reason": "入口iframe和图片相邻简介结构均由静态HTML提供"},
    },
}


def normalize_layout(text: str) -> str:
    """确定性清理富文本编辑器产生的中文排版空白。"""
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def fetch_frame_html(main_html: str, final_url: str) -> str:
    """从入口iframe动态解析地址并通过公共增强请求抓取正文。"""
    soup = BeautifulSoup(main_html, "html.parser")
    frame = soup.select_one("iframe#dataList[src]")
    frame_url = urljoin(final_url, str(frame.get("src", "")).strip()) if frame else ""
    if not frame_url or frame_url == final_url:
        raise RuntimeError("入口页未发现有效的iframe#dataList地址")

    from crawler_core.fetcher import fetch_html_with_strategy

    return fetch_html_with_strategy(frame_url, strategy="requests").html


def first_text_after_image(image_paragraph: Tag) -> str:
    """只在当前图片段与下一图片段之间读取首个非空文本段。"""
    sibling = image_paragraph.find_next_sibling()
    while isinstance(sibling, Tag):
        if sibling.find("img") is not None:
            return ""
        if sibling.name == "p":
            text = normalize_layout(sibling.get_text(" ", strip=True))
            if text:
                return text
        sibling = sibling.find_next_sibling()
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按#jgcon3人物图片顺序提取其后第一行姓名和完整现任句。"""
    soup = BeautifulSoup(fetch_frame_html(html, final_url), "html.parser")
    region = soup.select_one("#jgcon3")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for image in region.select("p img"):
        image_paragraph = image.find_parent("p")
        if image_paragraph is None:
            continue
        text = first_text_after_image(image_paragraph)
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,8})，", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if name_match is None or evidence_match is None:
            continue
        name = name_match.group("name")
        if name in seen:
            continue
        seen.add(name)
        evidence = evidence_match.group(0)
        duty = evidence.removeprefix("现任").removesuffix("。").strip()
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "入口iframe#dataList动态取src；frame #jgcon3按人物图片DOM顺序，只读下一图片前首个非空p中的姓名与完整现任句",
            }
        )
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
