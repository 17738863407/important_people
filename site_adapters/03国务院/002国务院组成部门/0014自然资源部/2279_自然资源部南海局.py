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
    "rule_id": "2279",
    "page_type": "人物列表完整页",
    "structure_group": "南海局主领导块及人物列表卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MnrSouthSeaLeaderWindowParser_v2",
    "leader_region_selector": ".dwgk-jgld .leader",
    "name_selector": "dt .name及.ldlist h4",
    "duty_selector": "dt .zw及.ldlist h5",
    "detail_link_selector": ".ldlist li a[href]",
    "detail_strategy": {"required": False, "mode": "available_card_link"},
    "risk_flag": "同区包含主领导块与普通卡片；主领导当前无人物链接，普通卡片链接为独立人物页；禁止固定人物表",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def _record(name: str, duty: str, detail_url: str) -> dict:
    return {
        "name": name,
        "duty": duty,
        "evidence": duty,
        "detail_url": detail_url,
        "parser": PAGE_RULE["parser"],
        "selector_summary": ".dwgk-jgld .leader；主块dt.name/zw及.ldlist卡片h4/h5",
    }


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按主领导块、后续人物卡片的DOM顺序动态解析。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".dwgk-jgld .leader")
    if region is None:
        raise RuntimeError("未找到领导之窗人物区域")
    records: list[dict] = []
    seen_names: set[str] = set()
    main_name_node = region.select_one("dl dt .name")
    main_duty_node = region.select_one("dl dt .zw")
    main_name = _clean_text(main_name_node.get_text(" ", strip=True) if main_name_node else "")
    main_duty = _clean_text(main_duty_node.get_text(" ", strip=True) if main_duty_node else "")
    if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", main_name) and main_duty:
        seen_names.add(main_name)
        records.append(_record(main_name, main_duty, ""))
    for card in region.select(".ldlist li"):
        name_node = card.select_one("h4")
        duty_node = card.select_one("h5")
        link_node = card.select_one("a[href]")
        name = _clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        href = str(link_node.get("href") or "").strip() if link_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        records.append(_record(name, duty, urljoin(base_url, href) if href else ""))
    if not records:
        raise RuntimeError("领导之窗未解析到人物记录")
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
