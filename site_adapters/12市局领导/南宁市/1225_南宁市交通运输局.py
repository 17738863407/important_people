from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1225",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_transport_list_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_list_then_detail_http",
    "parser": "page_nanning_transport_list_detail_v2",
    "leader_region_selector": ".nav1Cont ul.has_line",
    "name_selector": "详情简介段首个逗号前姓名",
    "duty_selector": "详情简介段内完整现任句",
    "detail_link_selector": ".nav1Cont ul.has_line li a[href]",
    "detail_strategy": {"required": True, "mode": "list_to_detail", "detail_link_selector": ".nav1Cont ul.has_line li a[href]", "max_detail_links": 30},
    "risk_flag": "页面可能含移动端重复列表；必须限定桌面端.has_line列表并保持顺序逐详情提取完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".nav1Cont ul.has_line", "detail_link_selector": "li a[href]", "detail_content_selector": ".TRS_UEDITOR, .TRS_Editor"},
        "api": {"enabled": False, "reason": "领导列表和一对一人物详情均由静态HTML提供"},
    },
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def discover_details(html: str, final_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select(".nav1Cont ul.has_line li a[href]"):
        url = urljoin(final_url, str(anchor.get("href", "")).strip())
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def parse_detail(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".TRS_UEDITOR, .TRS_Editor")
    if region is None:
        return "", ""
    for paragraph in region.select("p"):
        text = normalize_layout(paragraph.get_text(" ", strip=True))
        name_match = re.search(r"(?:个人简历：)?(?P<name>[\u4e00-\u9fff·]{2,8})，", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if name_match is not None and evidence_match is not None:
            evidence = evidence_match.group(0).removeprefix("现任").removesuffix("。")
            return name_match.group("name"), evidence
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    detail_urls = discover_details(html, final_url)
    if not detail_urls:
        return []
    from crawler_core.fetcher import fetch_html_with_strategy

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for detail_url in detail_urls:
        name, evidence = parse_detail(fetch_html_with_strategy(detail_url, strategy="requests").html)
        if not name or not evidence:
            raise RuntimeError(f"人物详情页缺少可验证的姓名或完整现任句：{detail_url}")
        if name in seen:
            continue
        seen.add(name)
        rows.append({
            "name": name,
            "duty": evidence,
            "evidence": evidence,
            "detail_url": detail_url,
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": "桌面端.nav1Cont ul.has_line人物链接按DOM顺序；逐详情简介段提取段首姓名与完整现任句",
        })
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
