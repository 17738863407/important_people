from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3226",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_emergency_duty_colon_name_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_http",
    "parser": "page_nanning_emergency_duty_colon_name_v2",
    "leader_region_selector": "领导班子职务：姓名人物链接列表",
    "name_selector": "人物链接冒号后姓名",
    "duty_selector": "同一人物链接完整原文",
    "detail_link_selector": "人物链接href",
    "detail_strategy": {"required": False, "mode": "list_direct_with_detail_url", "max_detail_links": 30},
    "risk_flag": "页面含导航噪声；只接受链接内完整职务：姓名结构，不给原始职务补写机构名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "领导班子人物链接列表", "name_selector": "链接冒号后姓名", "duty_selector": "同一链接完整原文", "detail_link_selector": "人物链接href"}, "api": {"enabled": False, "reason": "领导列表静态提供职务、姓名和详情链接"}},
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        evidence = normalize_layout(anchor.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>[^：:]{2,100})[：:](?P<name>[\u4e00-\u9fff·]{2,8})", evidence)
        if match is None or re.search(r"(?:书记|局长|主任|党委委员|调研员)", match.group("duty")) is None:
            continue
        name = match.group("name")
        detail_url = urljoin(final_url, str(anchor.get("href", "")).strip())
        if name in seen or not detail_url or detail_url == final_url:
            continue
        seen.add(name)
        duty = match.group("duty")
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "parser": str(page_rule.get("parser", "")), "selector_summary": "领导班子职务：姓名人物链接按DOM顺序；保留左侧职务"})
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
