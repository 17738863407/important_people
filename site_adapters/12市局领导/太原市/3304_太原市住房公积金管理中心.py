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
    "rule_id": "3304",
    "page_type": "人物目录详情页",
    "structure_group": "taiyuan_housing_fund_online_details_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_housing_fund_online_details_v2",
    "leader_region_selector": ".box_list",
    "name_selector": "ul li > a[href][title]",
    "duty_selector": "人物详情页#Zoom唯一非空段落",
    "detail_link_selector": "ul li > a[href][title]",
    "detail_strategy": {"required": True, "mode": "online_list_to_detail"},
    "risk_flag": "目录页仅列姓名，原始职务必须在线逐人物详情页提取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并HTML排版空白，保留详情职务原文与标点。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def fetch_detail_soup(session: requests.Session, detail_url: str) -> BeautifulSoup:
    """在线取得详情页；仅在证书校验失败时执行SSL降级重试。"""
    try:
        response = session.get(detail_url, timeout=30)
    except requests.exceptions.SSLError:
        response = session.get(detail_url, timeout=30, verify=False)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return BeautifulSoup(response.text, "html.parser")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按目录DOM顺序在线读取人物详情页中的唯一职务正文。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select(".box_list")
    if len(regions) != 1:
        raise RuntimeError(f"领导目录区域数量异常：{len(regions)}")
    base_url = final_url or page_rule["url"]
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": base_url})

    records: list[object] = []
    seen_names: set[str] = set()
    for link in regions[0].select("ul li > a[href][title]"):
        name = re.sub(r"\s+", "", str(link.get("title") or ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            raise RuntimeError(f"目录姓名结构异常：{name}")
        if name in seen_names:
            raise RuntimeError(f"目录姓名重复：{name}")
        detail_url = urljoin(base_url, str(link.get("href") or ""))
        if not detail_url or detail_url.rstrip("/") == base_url.rstrip("/"):
            raise RuntimeError(f"人物详情链接异常：{name}")
        detail_soup = fetch_detail_soup(session, detail_url)
        paragraphs = [
            clean_text(node.get_text(" ", strip=True))
            for node in detail_soup.select("#Zoom p")
            if clean_text(node.get_text(" ", strip=True))
        ]
        if len(paragraphs) != 1:
            raise RuntimeError(f"人物详情职务段数量异常：{name}={len(paragraphs)}")
        evidence = paragraphs[0]
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导目录没有可验证人物链接")
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
