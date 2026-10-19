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
    """构造不含业务源硬编码的页面规则。"""
    return {
        "rule_id": rule_id,
        "domain": "gdaudit.gd.gov.cn",
        "page_type": "人物目录详情页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "raw_http",
        "extract_mode": "list_to_detail",
        "collector": "raw_http",
        "parser": "gdaudit_leader_detail_present_v1",
        "leader_region_selector": '.con .GsTL5 a[href*="/ldcy/content/"]',
        "name_selector": '.con .GsTL5 a[href*="/ldcy/content/"]',
        "duty_selector": "详情页 .con 文本中最后一个完整现任句",
        "detail_link_selector": '.con .GsTL5 a[href*="/ldcy/content/"]',
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
            "detail_link_selector": '.con .GsTL5 a[href*="/ldcy/content/"]',
            "detail_parser": "gdaudit_detail_present_duty_v1",
            "detail_name_selector": "目录页链接文本",
            "detail_duty_selector": "详情页 .con 最后一个完整现任句",
            "detail_content_selector": ".con",
            "max_detail_links": 50,
        },
        "risk_flag": "入口页会按请求头跳转移动版，必须保留桌面入口原始HTTP响应",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": '.con .GsTL5 a[href*="/ldcy/content/"]',
                "name_selector": '.con .GsTL5 a[href*="/ldcy/content/"]',
                "duty_selector": "详情页 .con 最后一个完整现任句",
                "detail_link_selector": '.con .GsTL5 a[href*="/ldcy/content/"]',
                "content_scope": {
                    "start_anchor": "",
                    "end_anchor": "",
                    "include_selectors": [],
                    "exclude_selectors": [],
                },
            },
            "api": {"enabled": False, "reason": "在线目录与人物详情页逐页解析"},
        },
    }


def clean_text(value: str) -> str:
    """压缩网页排版空白。"""
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", text)


def fetch_detail_html(detail_url: str, timeout: int) -> str:
    """在线读取人物详情页。"""
    response = requests.get(
        detail_url,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/145.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text


def parse_detail_page(html: str) -> tuple[str, str]:
    """返回最后一个完整“现任……”句及其职务文本。"""
    soup = BeautifulSoup(html or "", "html.parser")
    content = soup.select_one(".con") or soup
    text = clean_text(content.get_text(" ", strip=True))
    matches = list(re.finditer(r"现任[^。]*。", text))
    if not matches:
        return "", ""
    evidence = matches[-1].group(0)
    duty = evidence.removeprefix("现任").rstrip("。")
    return duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析广东省审计厅在线领导目录，并逐页读取现任职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.con .GsTL5 a[href*=ldcy/content]；"
        "name=目录页链接文本；duty=在线详情.con最后一个完整现任句"
    )
    for anchor in soup.select('.con .GsTL5 a[href*="/ldcy/content/"]'):
        name = clean_text(anchor.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5·]{2,4}", name) or name in seen_names:
            continue
        seen_names.add(name)
        detail_url = urljoin(final_url, str(anchor.get("href") or ""))
        try:
            duty, evidence = parse_detail_page(fetch_detail_html(detail_url, timeout=20))
        except requests.RequestException:
            duty, evidence = "", ""
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
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
    rule_id_value = "0659"
    main(rule_id_value)
