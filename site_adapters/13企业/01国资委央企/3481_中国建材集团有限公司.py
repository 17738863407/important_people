from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3481",
    "page_type": "人物列表完整页",
    "structure_group": "建材集团四类公司领导人物卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http_navigation",
    "parser": "CnbmCurrentLeaderCardParser_v1",
    "leader_region_selector": "四个公司领导版块页面的.leader-inner li",
    "name_selector": ".leader-name",
    "duty_selector": ".leader-zc",
    "detail_link_selector": "a[href*='about-leader-detail.html?leader=']",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "旧规则入口已重定向首页；从当前cnbm-data.js动态发现四个公司领导版块路由，同名人物职务按页面原文去重合并",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def _fetch_leader_sections(html: str, base_url: str) -> list[tuple[str, str, str]]:
    """从当前网站脚本动态发现并抓取四个公司领导版块。"""
    soup = BeautifulSoup(html, "html.parser")
    script_node = soup.select_one("script[src*='cnbm-data.js']")
    if script_node is None:
        raise RuntimeError("建材集团官网未发现当前数据路由脚本")
    script_url = urljoin(base_url, str(script_node.get("src", "")))
    script_response = requests.get(
        script_url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        timeout=30,
    )
    script_response.raise_for_status()
    route_order = ("team", "party", "board", "management")
    route_matches = re.findall(
        r'["\']([^"\']*about-leaders-(team|party|board|management)\.html)["\']',
        script_response.text,
    )
    route_urls: dict[str, str] = {}
    for route, section_key in route_matches:
        route_urls.setdefault(section_key, urljoin(base_url, route))
    missing = [section_key for section_key in route_order if section_key not in route_urls]
    if missing:
        raise RuntimeError(f"建材集团数据脚本缺少公司领导版块路由：{', '.join(missing)}")

    sections: list[tuple[str, str, str]] = []
    for section_key in route_order:
        section_response = requests.get(
            route_urls[section_key],
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=30,
        )
        section_response.raise_for_status()
        section_response.encoding = section_response.apparent_encoding or section_response.encoding
        sections.append((section_key, section_response.text, section_response.url))
    return sections


def _merge_duty_parts(existing_parts: list[str], duty: str) -> None:
    """按网页出现顺序合并职务组成项，并消除跨版块重复。"""
    for part in re.split(r"[、，,]", duty):
        cleaned_part = _clean_text(part)
        if cleaned_part and cleaned_part not in existing_parts:
            existing_parts.append(cleaned_part)


def _build_detail_url(section_url: str, href: str, section_key: str) -> str:
    """还原网页脚本为人物详情链接添加的版块参数。"""
    detail_url = urljoin(section_url, href)
    parts = urlsplit(detail_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["tab"] = section_key
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按四个版块顺序解析人物，同名人物合并各版块原始职务。"""
    merged_records: dict[str, dict] = {}
    section_counts: dict[str, int] = {}
    for section_key, section_html, section_url in _fetch_leader_sections(html, base_url):
        soup = BeautifulSoup(section_html, "html.parser")
        cards = soup.select(".leader-inner li")
        section_counts[section_key] = len(cards)
        if not cards:
            raise RuntimeError(f"建材集团公司领导版块未解析到人物卡片：{section_key}")
        for card in cards:
            name_node = card.select_one(".leader-name")
            duty_node = card.select_one(".leader-zc")
            if name_node is None or duty_node is None:
                raise RuntimeError(f"建材集团公司领导卡片缺少姓名或职务：{section_key}")
            name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
            duty = _clean_text(duty_node.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
                raise RuntimeError(f"建材集团公司领导卡片姓名或职务异常：{section_key}")
            link = card.select_one("a[href*='about-leader-detail.html?leader=']")
            detail_url = (
                _build_detail_url(section_url, str(link.get("href", "")), section_key)
                if link
                else ""
            )
            if name not in merged_records:
                merged_records[name] = {
                    "name": name,
                    "duty_parts": [],
                    "detail_url": detail_url,
                }
            _merge_duty_parts(merged_records[name]["duty_parts"], duty)

    expected_sections = {"team", "party", "board", "management"}
    if set(section_counts) != expected_sections:
        raise RuntimeError("建材集团公司领导四个版块未完整采集")

    records: list[dict] = []
    for item in merged_records.values():
        evidence = "；".join(item["duty_parts"])
        records.append(
            {
                "name": item["name"],
                "duty": evidence,
                "evidence": evidence,
                "detail_url": item["detail_url"],
                "parser": rule["parser"],
                "selector_summary": "动态发现并采集领导班子、党委常委、董事会、经理层成员及高管人员；同名职务去重合并",
            }
        )
    if not records:
        raise RuntimeError("建材集团四个公司领导版块未解析到人物记录")
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
