from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def normalize_space(text: str) -> str:
    """清理网页排版空白，不改变职务语义。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    """删除姓名节点中的纯排版空白。"""
    return re.sub(r"\s+", "", normalize_space(text))


def is_name(text: str) -> bool:
    """仅接受强结构姓名字段中的常见中文姓名形式。"""
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", text))


def build_page_rule(rule_id: str) -> dict:
    """构造当前页面经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "news.12371.cn",
        "page_type": "单人物领导首页",
        "structure_group": "12371_zzb_primary_leader_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "force_browser": True,
        "extract_mode": "single_leader_name_duty_direct",
        "collector": "static_http",
        "parser": "page_12371_zzb_primary_leader_v1",
        "leader_region_selector": ".ind_01_gerenjianjie",
        "name_selector": "h2 a",
        "duty_selector": "h3",
        "detail_link_selector": "",
        "content_scope": {
            "include_selectors": [".ind_01_gerenjianjie"],
            "exclude_selectors": ["script", "style"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "detail_link_selector": "",
            "candidate_links": [],
        },
        "risk_flag": "http_returns_thanks_page_force_browser",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".ind_01_gerenjianjie",
                "name_selector": "h2 a",
                "duty_selector": "h3",
            },
            "api": {"enabled": False, "reason": "静态HTML领导区域已直接包含姓名和职务"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从唯一领导区域提取姓名与网页原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".ind_01_gerenjianjie")
    if region is None:
        return []

    name_node = region.select_one("h2 a")
    duty_node = region.select_one("h3")
    if name_node is None or duty_node is None:
        return []

    name = clean_name(name_node.get_text(" ", strip=True))
    duty = normalize_space(duty_node.get_text(" ", strip=True)).strip(" ：:，,。.")
    if not is_name(name) or not duty:
        return []

    return [
        {
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": "",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": "strategy=custom_parse_page；region=.ind_01_gerenjianjie；fields=h2 a+h3",
        }
    ]


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        page_rule,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3549"
    main(rule_id_value)
