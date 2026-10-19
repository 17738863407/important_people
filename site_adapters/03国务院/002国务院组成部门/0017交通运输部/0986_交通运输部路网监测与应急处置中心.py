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
    "rule_id": "0986",
    "page_type": "人物列表完整页",
    "structure_group": "桌面端领导班子卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "HmrcDesktopLeaderCardParser_v2",
    "leader_region_selector": ".web_mode ul.lead_list_ul li",
    "name_selector": "span:first-of-type a[href]",
    "duty_selector": "span:nth-of-type(2)",
    "detail_link_selector": "span:first-of-type a[href]",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面同时输出桌面端与移动端重复领导DOM，必须仅解析web_mode；详情链接须与当前卡片一一对应",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按桌面端卡片DOM顺序抽取姓名、职务与独立人物详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select(".web_mode ul.lead_list_ul li"):
        spans = card.find_all("span", recursive=False)
        if len(spans) < 2:
            continue
        link_node = spans[0].select_one("a[href]")
        name = _clean_text(link_node.get_text(" ", strip=True)) if link_node else ""
        evidence = re.sub(
            r"[（(]\s*挂职\s*[）)]",
            "",
            _clean_text(spans[1].get_text(" ", strip=True)),
        ).strip()
        href = _clean_text(str(link_node.get("href", ""))) if link_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen_names:
            continue
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(base_url, href),
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".web_mode ul.lead_list_ul li；首span姓名链接；第二span职务",
            }
        )
    if not records:
        raise RuntimeError("桌面端领导班子卡片未解析到人物记录")
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
