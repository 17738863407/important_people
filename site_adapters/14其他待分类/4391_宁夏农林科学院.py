from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4391",
    "page_type": "科学院院领导图文简介页",
    "structure_group": "nxaas_leader_profile_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "raw_http",
    "parser": "custom_nxaas_current_leaders_v1",
    "leader_region_selector": ".gk-artcle-con .view",
    "name_selector": ".gk-artcle-con .view p strong",
    "duty_selector": ".gk-artcle-con .view p",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".gk-artcle-con .view"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名与简历及现职位于同一段，需在当前人物段内按机构现职句边界裁剪",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验5个加粗姓名简介段及段内宁夏农林科学院现职句",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".gk-artcle-con .view", "name_selector": ".gk-artcle-con .view p strong", "duty_selector": ".gk-artcle-con .view p", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".gk-artcle-con .view"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "院领导姓名、简历和现职直接呈现在HTML简介段中"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    if "宁夏农林科学院党组" not in html:
        session = requests.Session()
        session.trust_env = False
        response = session.get(str(page_rule.get("url", "")), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        html = response.text
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".gk-artcle-con .view")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in root.select("p"):
        strong_nodes = paragraph.select("strong")
        if not strong_nodes:
            continue
        name = clean_text("".join(node.get_text(" ", strip=True) for node in strong_nodes))
        full_text = clean_text(paragraph.get_text(" ", strip=True))
        duty_match = re.search(r"宁夏农林科学院[^。]*[。]", full_text)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or duty_match is None or name in seen:
            continue
        duty = duty_match.group(0).rstrip("。")
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": ".gk-artcle-con .view人物段内机构现职句"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
