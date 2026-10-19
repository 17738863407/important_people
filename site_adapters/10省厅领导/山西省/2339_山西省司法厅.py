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
    "rule_id": "2339",
    "domain": "sft.shanxi.gov.cn",
    "page_type": "人物目录详情页",
    "structure_group": "",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "V011_directory_link_v1",
    "leader_region_selector": "html > body > div.zwxxgk_bd:nth-of-type(1)",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
        "candidate_links": [],
    },
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    
    "locator_strategy": "css",
    "locator": {
        "css": {
            "leader_region_selector": "html > body > div.zwxxgk_bd:nth-of-type(1)",
            "name_selector": "",
            "duty_selector": "",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "未发现或未配置可复现接口，沿用 CSS/HTML 定位"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "pending_root",
            "behavior_changed": False,
        },
    },
}


def normalize_text(value: str) -> str:
    """合并网页文本中的空白，保留原始标点和职务表述。"""
    return re.sub(r"\s+", "", value or "").strip()


def fetch_detail_text(detail_url: str) -> str:
    """在线读取独立人物详情页并返回可检索的正文文本。"""
    response = requests.get(
        detail_url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    if response.encoding and response.encoding.lower() in {"iso-8859-1", "latin-1"}:
        response.encoding = "utf-8"
    detail_soup = BeautifulSoup(response.text, "html.parser")
    content = detail_soup.select_one("div.trs_editor_view") or detail_soup
    return normalize_text(content.get_text("", strip=True))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从领导目录动态发现详情页，并提取网页中的完整现任职务句。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div.zfxxgk_zdgkc")
    if region is None:
        return []

    rows: list[dict] = []
    seen_urls: set[str] = set()
    for anchor in region.select("a[href]"):
        href = anchor.get("href", "").strip()
        detail_url = urljoin(final_url or page_rule["url"], href)
        if not re.search(r"/zzjg/ldxx/\d{6}/t\d+_\d+\.html$", detail_url):
            continue
        if detail_url in seen_urls:
            continue

        name = normalize_text(anchor.get("title") or anchor.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue

        detail_text = fetch_detail_text(detail_url)
        evidence_match = re.search(r"现任[^。]*。", detail_text)
        if evidence_match is None:
            continue

        evidence = evidence_match.group(0).removeprefix("现任").removesuffix("。")
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": detail_url,
                "order": str(len(rows) + 1),
            }
        )
        seen_urls.add(detail_url)
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
