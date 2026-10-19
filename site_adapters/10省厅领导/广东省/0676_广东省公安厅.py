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


def build_page_rule(rule_id: str) -> dict:
    """构造不含业务源和人物候选硬编码的页面规则。"""
    return {
        "rule_id": rule_id,
        "domain": "gdga.gd.gov.cn",
        "page_type": "人物表格页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "接口数据加载",
        "fetch_mode": "online",
        "extract_mode": "list_to_detail",
        "collector": "browser_dom",
        "parser": "page_online_gdga_detail_prefix_duty_v1",
        "leader_region_selector": "a.document-number[href]",
        "name_selector": "a.document-number链接文本",
        "duty_selector": "在线详情页姓名性别句中姓名前文本",
        "detail_link_selector": "a.document-number[href]",
        "content_scope": {
            "start_anchor": "",
            "end_anchor": "",
            "include_selectors": [],
            "exclude_selectors": [],
        },
        "detail_strategy": {
            "required": True,
            "mode": "custom_parse_page_fetch_detail",
            "detail_collector_type": "static_http",
            "detail_link_selector": "a.document-number[href]",
            "detail_parser": "gdga_detail_prefix_duty_v1",
            "detail_name_selector": "目录页链接文本",
            "detail_duty_selector": "详情页姓名前职务",
            "detail_content_selector": ".article-content",
            "max_detail_links": 50,
        },
        "risk_flag": "",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "weak_allow_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "a.document-number[href]",
                "name_selector": "a.document-number链接文本",
                "duty_selector": "在线详情页姓名性别句中姓名前文本",
                "detail_link_selector": "a.document-number[href]",
                "content_scope": {
                    "start_anchor": "",
                    "end_anchor": "",
                    "include_selectors": [],
                    "exclude_selectors": [],
                },
            },
            "api": {"enabled": False, "reason": "在线浏览器 DOM 名单与在线详情页逐页解析"},
        },
    }


def clean_text(value: str) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "")


def fetch_detail_html(detail_url: str, referer: str) -> str:
    """在线读取人物详情页。"""
    response = requests.get(
        detail_url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": referer},
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def extract_duty(detail_html: str, name: str) -> str:
    """从详情页姓名性别句提取姓名前的网页原始职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    for paragraph in soup.select(".article-content p, p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.search(rf"^(?P<duty>.+?){re.escape(name)}[，,](?:男|女)[，,]", text)
        if match:
            return match.group("duty").strip("：:，,、；;。")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析广东省公安厅在线领导名单与详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a.document-number[href]"):
        name = clean_text(link.get_text(" ", strip=True))
        name = re.sub(r"简历$", "", name)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, link.get("href") or "")
        try:
            duty = extract_duty(fetch_detail_html(detail_url, final_url), name)
        except requests.RequestException:
            duty = ""
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "a.document-number在线姓名+详情页姓名性别句前原职务",
            }
        )
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(build_page_rule(rule_id), globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "0676"
    main(rule_id_value)
