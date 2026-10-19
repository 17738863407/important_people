from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0574",
    "page_type": "人物表格页",
    "structure_group": "haikou_ftz_leader_list_detail_basic_info",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".lby.clear领导信息块",
    "name_selector": ".lby-lm2 a[title]",
    "duty_selector": "详情页#zoom .content基本信息字段",
    "detail_link_selector": ".lby-lm2 a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "机构职能",
        "include_selectors": [".lby.clear"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": True, "mode": "detail_page", "max_detail_links": 50},
    "risk_flag": "只遍历领导信息块动态人物链接，详情页以基本信息和分工标签划定职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_detail(detail_html: str, expected_name: str) -> tuple[str, str]:
    soup = BeautifulSoup(detail_html, "html.parser")
    heading = soup.select_one(".center-context-right .content-title")
    content = soup.select_one("#newContent1")
    name = clean_text(heading.get_text(" ", strip=True) if heading else "")
    text = clean_text(content.get_text(" ", strip=True) if content else "")
    if name != expected_name:
        raise ValueError(f"详情页姓名与列表不一致：{expected_name} -> {name or '空'}")
    match = re.search(r"基本信息[：:]\s*(?P<duty>.*?)(?=\s*分工[：:]|$)", text)
    duty = clean_text(match.group("duty")) if match else ""
    if not duty:
        raise ValueError(f"详情页基本信息字段为空：{name}")
    # “基本信息”是字段标签，不属于职务原文。
    return duty, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url") or final_url or "")
    rows: list[dict[str, str]] = []
    for block in soup.select(".lby.clear"):
        heading = block.select_one(".lby-lm1")
        if clean_text(heading.get_text(" ", strip=True) if heading else "") != "领导信息":
            continue
        for link in block.select(".lby-lm2 a[href]"):
            name = clean_text(link.get("title") or link.get_text(" ", strip=True)).lstrip("· ")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
                raise ValueError("领导信息块出现无法验证的人物链接文本")
            detail_url = urljoin(final_url or source_url, str(link.get("href") or ""))
            response = requests.get(detail_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            duty, evidence = parse_detail(response.text, name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": evidence,
                    "detail_url": detail_url,
                    "selector_summary": "领导信息块动态人物链接及详情页基本信息字段",
                }
            )
    if not rows:
        raise ValueError("入口页未发现可验证的领导信息链接")
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
