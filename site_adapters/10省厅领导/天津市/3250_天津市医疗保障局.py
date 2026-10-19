from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3250",
    "page_type": "人物目录详情页",
    "structure_group": "tianjin_medical_security_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_medical_security_directory_details_v1",
    "leader_region_selector": "#ownChannelsDocs",
    "name_selector": "#ownChannelsDocs a[href]",
    "duty_selector": "详情页.trs_editor_view首个姓名段",
    "detail_link_selector": "#ownChannelsDocs a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": ["#ownChannelsDocs", ".trs_editor_view"],
        "exclude_selectors": ["发文日期", "主持", "分管", "联系"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "directory_details",
        "detail_collector_type": "static_http",
        "detail_link_selector": "#ownChannelsDocs a[href]",
        "detail_name_selector": ".trs_editor_view首个姓名段",
        "detail_duty_selector": ".trs_editor_view首个姓名段中姓名后的原文",
        "detail_content_selector": ".trs_editor_view",
        "max_detail_links": 50,
    },
    "risk_flag": "详情首段使用机构简称且个别HTML含空锚点；只做排版清理并保留原文，不扩写简称，不采集后续主持、简历或分管内容",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#ownChannelsDocs",
            "name_selector": "a[href]",
            "duty_selector": "详情页.trs_editor_view p首个姓名段",
            "detail_link_selector": "a[href]",
            "content_scope": {
                "start_anchor": "姓名",
                "end_anchor": "下一正文段",
                "include_selectors": [".trs_editor_view p"],
                "exclude_selectors": ["主持", "男，", "分管", "联系"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML目录与详情正文可直接稳定提供所需字段",
        },
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u2002", " ").replace("\u200b", "").replace("\ufeff", "")
    text = text.replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def _fetch_detail(url: str) -> tuple[str, str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _extract_detail_duty(html: str, expected_name: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for paragraph in soup.select(".trs_editor_view p"):
        text = _clean_text(paragraph.get_text("", strip=True))
        compact_text = re.sub(r"\s+", "", text)
        if not compact_text.startswith(expected_name):
            continue
        duty = compact_text[len(expected_name) :]
        return duty.strip()
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导目录DOM顺序在线解析详情首段中的原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("#ownChannelsDocs a[href]"):
        name = _clean_name(str(link.get("title", "")) or link.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        requested_url = urljoin(base_url, str(link.get("href", "")))
        detail_html, detail_url = _fetch_detail(requested_url)
        duty = _extract_detail_duty(detail_html, name)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_medical_security_directory_details_v1",
                "selector_summary": "#ownChannelsDocs目录；详情.trs_editor_view首个姓名段",
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
