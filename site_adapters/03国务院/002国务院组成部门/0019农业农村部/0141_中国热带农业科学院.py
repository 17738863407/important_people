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


PAGE_RULE = {
    "rule_id": "0141", "page_type": "多人物详情合并页", "structure_group": "catas_leader_list_detail_v2", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_catas_leader_list_detail_v2",
    "leader_region_selector": "div.right div.title + div.listbox li", "name_selector": "a[href]", "duty_selector": "detail article or div.article_con", "detail_link_selector": "a[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["div.right div.title + div.listbox"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": True, "mode": "custom_list_to_detail", "detail_collector_type": "static_http", "detail_link_selector": "a[href]", "detail_parser": "page_inline_detail_short_duty", "detail_name_selector": "", "detail_duty_selector": "article or div.article_con", "detail_content_selector": "article, div.article_con", "max_detail_links": 20},
    "risk_flag": "详情正文同时含履历；仅接受详情article或article_con开头的短职务块，排除基本信息之后内容", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "weak_allow_wordlist", "locator_strategy": "page_inline_list_to_detail_short_duty",
    "locator": {"css": {"leader_region_selector": "div.right div.title + div.listbox li", "name_selector": "a[href]", "detail_content_selector": "article, div.article_con"}, "api": {"enabled": False, "reason": "列表页与详情页静态HTML可复现"}, "migration": {"source": "legacy_business_source_and_offline_dependency_removed", "verified_status": "verified_current_raw_http_and_details", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").replace("\u3000", " ").split())


def looks_like_duty(value: str) -> bool:
    duty_words = ("院长", "党组", "纪检", "成员", "书记", "秘书长", "主任")
    noise_words = ("当前位置", "作者", "来源", "日期", "点击", "打印", "分享")
    return any(word in value for word in duty_words) and not any(word in value for word in noise_words)


def extract_detail_duty(html: str) -> str:
    """从当前详情页的短职务块提取原文，停止于履历字段。"""
    for fragment in re.findall(r"<article[\s\S]*?</article>", html, flags=re.IGNORECASE):
        text = clean_text(BeautifulSoup(fragment.replace("\\/", "/"), "html.parser").get_text(" ", strip=True))
        if looks_like_duty(text) and len(text) <= 80:
            return text
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select("div.article_con p, div.article_con div, div.article_con"):
        text = clean_text(node.get_text(" ", strip=True))
        for marker in ("基本信息", "任职信息", "主要研究"):
            if marker in text:
                text = clean_text(text.split(marker, 1)[0])
        if looks_like_duty(text) and len(text) <= 80:
            return text
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select(page_rule["leader_region_selector"]):
        link = item.select_one(page_rule["name_selector"])
        if link is None:
            continue
        name = clean_text(link.get_text(" ", strip=True))
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not href:
            continue
        detail_url = urljoin(final_url, href)
        try:
            detail_result = fetch_by_raw_requests(detail_url, timeout=30)
            duty = extract_detail_duty(detail_result.html)
        except Exception:
            duty = ""
        if not duty:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_list_to_detail；scope=current_detail_short_duty；order=list_dom"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
