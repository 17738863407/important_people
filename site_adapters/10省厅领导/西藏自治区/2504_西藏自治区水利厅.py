from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "2504",
    "page_type": "人物目录详情页",
    "structure_group": "xizang_slt_leader_directory_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "raw_http",
    "parser": "custom_xizang_slt_leader_directory_detail_v2",
    "leader_region_selector": ".gl-main-list",
    "detail_link_selector": ":scope > li > p > a[href]",
    "detail_content_selector": ".right-desc",
    "detail_name_selector": ":scope > p.name",
    "detail_profile_selector": ":scope > p.desc",
    "detail_timeout_seconds": 25,
    "risk_flag": "部分详情页当前未发布职务正文，可靠姓名仍保留且依据说明留空",
    "confidence": "medium",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    """清除网页排版空白，不改变正文语义。"""
    return re.sub(r"\s+", "", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def _clean_current_evidence(value: str) -> str:
    """仅删除已定位现职句句首的“现任”固定标签。"""
    return re.sub(r"^现任(?:职务)?\s*[：:]?\s*", "", value, count=1)


def _is_valid_detail_url(source_url: str, detail_url: str) -> bool:
    """只接受入口同源且位于厅领导目录下的独立人物详情页。"""
    source = urlparse(source_url)
    detail = urlparse(detail_url)
    if detail.netloc != source.netloc:
        return False
    return bool(re.fullmatch(r"/jgzn/tld/\d{6}/t\d{8}_\d+\.html", detail.path))


def _fetch_detail_html(detail_url: str, timeout_seconds: int) -> tuple[str, str]:
    """通过项目公共采集器读取详情页，继承统一重试、编码及错误链路。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    result = fetch_html_with_strategy(
        detail_url,
        strategy="raw_http",
        timeout=timeout_seconds,
    )
    return result.html, result.final_url or detail_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按入口目录顺序抓取并解析每个真实独立人物详情页。"""
    list_soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    region_selector = str(page_rule["leader_region_selector"])
    link_selector = str(page_rule["detail_link_selector"])
    detail_selector = str(page_rule["detail_content_selector"])
    detail_name_selector = str(page_rule["detail_name_selector"])
    profile_selector = str(page_rule["detail_profile_selector"])
    timeout_seconds = int(page_rule["detail_timeout_seconds"])
    region = list_soup.select_one(region_selector)
    if region is None:
        raise RuntimeError(f"入口页未命中领导目录：{region_selector}")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    seen_links: set[str] = set()
    for link in region.select(link_selector):
        link_name = _clean_text(link.get_text("", strip=True))
        href = str(link.get("href", "")).strip()
        detail_url = urljoin(final_url or source_url, href)
        if not re.fullmatch(r"[\u3400-\u9fff]{2,4}", link_name):
            continue
        if not _is_valid_detail_url(source_url, detail_url):
            continue
        if link_name in seen_names or detail_url in seen_links:
            continue

        detail_html, fetched_url = _fetch_detail_html(detail_url, timeout_seconds)
        if not _is_valid_detail_url(source_url, fetched_url):
            raise RuntimeError(f"详情页发生异常跳转：{link_name} -> {fetched_url}")
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        detail_region = detail_soup.select_one(detail_selector)
        if detail_region is None:
            raise RuntimeError(f"详情页未命中人物区域：{link_name} -> {fetched_url}")
        name_node = detail_region.select_one(detail_name_selector)
        detail_name = _clean_text(name_node.get_text("", strip=True)) if name_node else ""
        if detail_name != link_name:
            raise RuntimeError(f"入口与详情姓名不一致：{link_name} != {detail_name}")

        profile_text = _clean_text(
            "".join(node.get_text("", strip=True) for node in detail_region.select(profile_selector))
        )
        evidence_match = re.search(r"现任[^。]{2,200}。", profile_text)
        evidence = _clean_current_evidence(evidence_match.group(0)) if evidence_match else ""
        seen_names.add(link_name)
        seen_links.add(detail_url)
        rows.append(
            {
                "name": detail_name,
                "duty": "",
                "detail_url": fetched_url,
                "evidence": evidence,
                "parser": str(page_rule["parser"]),
                "selector_summary": (
                    f"入口={region_selector} {link_selector}；"
                    f"详情={detail_selector} {detail_name_selector}+{profile_selector}"
                ),
            }
        )

    if not rows:
        raise RuntimeError("入口页未取得可验证人物详情链接")
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
