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
    "rule_id": "0840",
    "domain": "gzw.ln.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "public_directory_to_org_profile_role_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_verified_profile",
    "collector": "static_http",
    "parser": "page_inline_public_directory_to_org_profile_role_v1",
    "leader_region_selector": ".provincial-leaders-inner",
    "detail_link_selector": ".ldname a[href][title]",
    "profile_index_path": "/gzw/zzjg/index.shtml",
    "profile_link_selector": "p.govzzTtext a[href][title]",
    "profile_name_selector": ".govld3rtt1",
    "profile_duty_selector": ".govld3rtt2",
    "detail_strategy": {"required": True, "mode": "public_detail_with_org_profile_evidence"},
    "risk_flag": "部分信息公开详情仅有简历无职务；职务须由同站组织机构委领导强字段核定",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩目录和详情中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """移除姓名节点中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def fetch_html(url: str, attempt_offset: int) -> str:
    """通过公共原始HTTP采集器取得静态页面。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    return fetch_by_raw_requests(url, timeout=40, attempt_offset=attempt_offset).html


def fetch_profile_links(final_url: str, page_rule: dict[str, object]) -> dict[str, str]:
    """从同站组织机构页动态建立姓名到委领导详情的技术链接索引。"""
    profile_index_url = urljoin(final_url, str(page_rule.get("profile_index_path", "")))
    soup = BeautifulSoup(fetch_html(profile_index_url, 1), "html.parser")
    links: dict[str, str] = {}
    for link in soup.select(str(page_rule.get("profile_link_selector", ""))):
        name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) and href and name not in links:
            links[name] = urljoin(profile_index_url, href)
    return links


def validate_public_detail(detail_url: str, expected_name: str, attempt_offset: int) -> bool:
    """确认主入口人物链接确实落到对应姓名的公开详情页。"""
    soup = BeautifulSoup(fetch_html(detail_url, attempt_offset), "html.parser")
    title = clean_name(soup.title.get_text(" ", strip=True) if soup.title else "")
    return title == expected_name


def fetch_profile_duty(
    profile_url: str,
    expected_name: str,
    page_rule: dict[str, object],
    attempt_offset: int,
) -> str:
    """从委领导详情的姓名和职务强字段读取原始职务。"""
    soup = BeautifulSoup(fetch_html(profile_url, attempt_offset), "html.parser")
    name_node = soup.select_one(str(page_rule.get("profile_name_selector", "")))
    duty_node = soup.select_one(str(page_rule.get("profile_duty_selector", "")))
    if name_node is None or duty_node is None:
        return ""
    if clean_name(name_node.get_text(" ", strip=True)) != expected_name:
        return ""
    return clean_text(duty_node.get_text(" ", strip=True))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按信息公开入口顺序输出人物，并以同站委领导强字段取得职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    source_url = str(page_rule.get("url", "")) or final_url
    profile_links = fetch_profile_links(final_url or source_url, page_rule)
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate(region.select(".ldname a[href][title]"), start=1):
        name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not href or name in seen:
            continue
        profile_url = profile_links.get(name, "")
        if not profile_url:
            continue
        detail_url = urljoin(final_url or source_url, href)
        try:
            if not validate_public_detail(detail_url, name, source_order + 1):
                continue
            duty = fetch_profile_duty(profile_url, name, page_rule, source_order + 9)
        except Exception:
            continue
        if not duty:
            continue
        evidence = re.sub(r"[（(]\s*(?:兼|挂职)\s*[）)]", "", duty).strip()

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；order=public directory .ldname；"
                    "detail=public link title verified；profile=org index dynamic name match；"
                    "duty=.govld3rtt2"
                ),
            }
        )

    return records


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
