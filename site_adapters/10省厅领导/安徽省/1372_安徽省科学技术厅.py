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

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def clean_duty(text: str) -> str:
    duty = normalize_space(text)
    duty = re.sub(r"\s+([、，,）)])", r"\1", duty)
    duty = re.sub(r"([（(、，,])\s+", r"\1", duty)
    return duty.rstrip("。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "kjt.ah.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "raw_http",
        "extract_mode": "leader_title_list_direct",
        "collector": "raw_http",
        "parser": "page_anhui_science_leader_title_list_v1",
        "leader_region_selector": ".xxgk_nav_list",
        "name_selector": ".xxgk_nav_list a.title text before （",
        "duty_selector": ".xxgk_nav_list a.title text inside （）",
        "detail_link_selector": ".xxgk_nav_list a.title[href]",
        "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".xxgk_nav_list"], "exclude_selectors": []},
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "detail_collector_type": "static_http",
            "detail_link_selector": "",
            "detail_parser": "",
            "detail_name_selector": "",
            "detail_duty_selector": "",
            "detail_content_selector": "",
            "max_detail_links": 0,
        },
        "risk_flag": "入口查询参数包含catId，必须保留原始HTTP响应，禁止跟随脚本跳转丢失目标栏目",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".xxgk_nav_list",
                "name_selector": ".xxgk_nav_list a.title text before （",
                "duty_selector": ".xxgk_nav_list a.title text inside （）",
                "detail_link_selector": ".xxgk_nav_list a.title[href]",
                "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".xxgk_nav_list"], "exclude_selectors": []},
            },
            "api": {"enabled": False, "reason": "领导简介列表标题直接包含姓名和职务"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".xxgk_nav_list")
    if not region:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    base_url = final_url or str(page_rule.get("url", ""))
    pattern = re.compile(r"^(?P<name>[\u4e00-\u9fff·\s]{2,8})[（(](?P<duty>[^）)]+)[）)]$")
    for link_node in region.select("a.title[href]"):
        text = normalize_space(link_node.get_text(" ", strip=True))
        match = pattern.match(text)
        if not match:
            continue
        name = clean_name(match.group("name"))
        duty = clean_duty(match.group("duty"))
        if name in seen_names or not is_name(name) or not duty or len(duty) > 80:
            continue
        href = str(link_node.get("href") or "").strip()
        detail_url = ""
        if href and not href.lower().startswith(("#", "javascript:")):
            candidate_url = urljoin(base_url, href)
            if candidate_url.rstrip("/") != base_url.rstrip("/"):
                detail_url = candidate_url
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.xxgk_nav_list；fields=a.title 姓名（职务）；detail_chain=0",
            }
        )
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    output_path = run_page_adapter(page_rule, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "1372"
    main(rule_id_value)
