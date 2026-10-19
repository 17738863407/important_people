from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1895',
 'domain': 'www.news.cn',
 'page_type': '职务分组名单页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_xinhua_cmc_groups_v1',
 'leader_region_selector': '.part05, .part07',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.part05, .part07',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面part05和part07为中央军事委员会分组'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_names(text: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fa5]{2,4}", text)


def extract_current_duty(detail_url: str, name: str) -> tuple[str, str]:
    """进入人物报道页的“查看简历”二级页面，提取“现任”原始职务。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    report_result = fetch_by_raw_requests(detail_url, timeout=30)
    report_soup = BeautifulSoup(report_result.html, "lxml")
    resume_icon = report_soup.select_one("a[href] img.resumeicon, a[href] img[src*='Resumeicon']")
    resume_link = resume_icon.find_parent("a", href=True) if resume_icon else None
    if resume_link is None:
        profile = report_soup.select_one("#detail")
        if profile is None:
            raise RuntimeError(f"{name}直接详情页未找到正文区域")
        match = re.search(r"现任\s*([^。！？!?]+)", clean_text(profile.get_text(" ", strip=True)))
        if match is None:
            raise RuntimeError(f"{name}直接详情页正文未找到“现任”职务")
        return match.group(1).strip(), report_result.final_url
    resume_url = urljoin(report_result.final_url, str(resume_link.get("href", "")))
    result = fetch_by_raw_requests(resume_url, timeout=30)
    for _ in range(3):
        redirect = re.search(r"(?:window\.)?location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]", result.html)
        if redirect is None:
            break
        next_url = urljoin(result.final_url, redirect.group(1))
        if next_url == result.final_url:
            break
        result = fetch_by_raw_requests(next_url, timeout=30)
    soup = BeautifulSoup(result.html, "lxml")
    profile = soup.select_one("#detail")
    if profile is None:
        raise RuntimeError(f"{name}简历页未找到正文区域")
    match = re.search(r"现任\s*([^。！？!?]+)", clean_text(profile.get_text(" ", strip=True)))
    if match is None:
        raise RuntimeError(f"{name}简历页正文未找到“现任”职务")
    return match.group(1).strip(), result.final_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    link_by_name = {}
    source_url = str(page_rule.get("url", ""))
    for link in soup.select(".part05 a, .part07 a"):
        link_text = clean_text(link.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        detail_url = urljoin(final_url or source_url, href) if href and not href.startswith(("#", "javascript:")) else ""
        detail_path = urlparse(detail_url).path
        is_report_page = re.fullmatch(r"/politics/leaders/[^/]+/index\.htm", detail_path)
        is_direct_resume = re.fullmatch(r"/politics/\d{8}/[^/]+/c\.html", detail_path)
        if not (is_report_page or is_direct_resume):
            detail_url = ""
        for name in parse_names(link_text):
            link_by_name[name] = detail_url

    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    groups: list[tuple[str, str, str]] = []
    main_group = soup.select_one(".part05")
    title_node = main_group.select_one(".lmt01") if main_group else None
    group_title = clean_text(title_node.get_text(" ", strip=True)) if title_node else ""
    if main_group:
        for block in main_group.select(".person-box"):
            match = re.match(r"^(?P<duty>[^：:\s]+)[：:\s]+(?P<names>.+)$", clean_text(block.get_text(" ", strip=True)))
            if match:
                groups.append((match.group("duty"), match.group("names"), group_title))
    for part in soup.select(".part07"):
        match = re.match(r"^(?P<duty>[^：:]+)[：:]\s*(?P<names>.+)$", clean_text(part.get_text(" ", strip=True)))
        if match:
            groups.append((clean_text(match.group("duty")), match.group("names"), ""))
    for duty, names_text, prefix in groups:
        for name in parse_names(names_text):
            key = (name, duty)
            if key in seen:
                continue
            seen.add(key)
            detail_url = link_by_name.get(name, "")
            if not detail_url:
                failure = f"抽取失败：{name}缺少带“查看简历”的人物详情页链接"
                rows.append({
                    "name": name,
                    "duty": failure,
                    "detail_url": "",
                    "evidence": failure,
                    "confidence": "low",
                    "selector_summary": "新华网中央军事委员会职务分组",
                })
                continue
            try:
                duty, detail_url = extract_current_duty(detail_url, name)
            except RuntimeError as exc:
                failure = f"抽取失败：{exc}"
                rows.append({
                    "name": name,
                    "duty": failure,
                    "detail_url": "",
                    "evidence": failure,
                    "confidence": "low",
                    "selector_summary": "新华网中央军事委员会职务分组",
                })
                continue
            rows.append({
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "selector_summary": "新华网中央军事委员会职务分组",
            })
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
