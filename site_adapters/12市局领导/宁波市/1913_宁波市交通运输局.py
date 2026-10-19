from __future__ import annotations

import re
import sys
from pathlib import Path

import requests


PAGE_RULE = {
    "rule_id": "1913", "page_type": "人物目录详情页", "structure_group": "www_ningbo_gov_cn_live_api_leader_detail_v2", "reuse_scope": "www.ningbo.gov.cn领导信息栏目", "load_mode": "接口数据加载", "fetch_mode": "online", "extract_mode": "custom_parse_page", "collector": "online_http", "parser": "page_www_ningbo_live_api_leader_detail_v2",
    "leader_region_selector": "page/build/unit分页接口人物列表", "name_selector": "接口人物链接文本及详情姓名字段", "duty_selector": "详情页职务字段", "detail_link_selector": "接口返回的同栏目/art/人物链接", "detail_strategy": {"required": True, "mode": "live_api_to_detail", "max_detail_links": 80}, "risk_flag": "入口HTML不含人物列表；必须实时请求页面声明的page/build/unit接口并逐页读取详情职务字段", "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "page/build/unit分页接口人物列表", "name_selector": "详情姓名字段", "duty_selector": "详情职务字段", "detail_link_selector": "同栏目/art/人物链接"}, "api": {"enabled": True, "reason": "入口页script声明稳定page/build/unit分页接口"}},
}


def clean_evidence_duty(value: str) -> str:
    """删除独立状态标记，并归一当前页中文标点前后的排版空格。"""
    evidence = re.sub(r"(?:（兼）|\(兼\)|[<＜]兼[>＞])", "", value).strip()
    evidence = re.sub(r"\s+([，。；：、])", r"\1", evidence)
    return re.sub(r"([，；：、])\s+", r"\1", evidence).strip()


def fetch_detail_html(url: str) -> str:
    """读取证书链不完整的宁波领导详情页。"""
    response = requests.get(url, timeout=25, verify=False, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.www_ningbo_gov_cn_leader_info import _collect_live_api_links, _collect_page_and_api_links, _parse_detail_page

    links = _collect_live_api_links(page_rule) or _collect_page_and_api_links(html, final_url)
    if not links:
        rendered = fetch_html_with_strategy(str(page_rule.get("url", "")), strategy="playwright", timeout=45)
        links = _collect_page_and_api_links(rendered.html, rendered.final_url)
    if not links:
        raise RuntimeError("宁波领导信息分页接口未返回人物链接")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for list_name, detail_url in links:
        try:
            detail_name, duty, _ = _parse_detail_page(fetch_detail_html(detail_url), list_name)
        except Exception as exc:
            raise RuntimeError(f"人物{list_name}详情页采集或解析失败：{exc}") from exc
        name = detail_name or list_name
        if not name or not duty:
            raise RuntimeError(f"人物{list_name}详情页缺少姓名或职务字段")
        if name in seen:
            continue
        seen.add(name)
        evidence = clean_evidence_duty(duty)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": detail_url, "parser": str(page_rule.get("parser", "")), "selector_summary": "入口页声明的page/build/unit接口顺序；详情页姓名和职务字段"})
    if not rows:
        raise RuntimeError("宁波领导详情未提取到有效人物记录")
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
