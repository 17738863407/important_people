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

PAGE_RULE = {'rule_id': '1894',
 'domain': 'www.news.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_xinhua_secretariat_v1',
 'leader_region_selector': '.part04 a',
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
 'locator': {'css': {'leader_region_selector': '.part04 a',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面part04为中央书记处书记分组'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def extract_current_duty(detail_url: str, name: str) -> tuple[str, str]:
    """进入人物报道页的“查看简历”二级页面，提取“现任”原始职务。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    report_result = fetch_by_raw_requests(detail_url, timeout=30)
    report_soup = BeautifulSoup(report_result.html, "lxml")
    resume_icon = report_soup.select_one("a[href] img.resumeicon, a[href] img[src*='Resumeicon']")
    resume_link = resume_icon.find_parent("a", href=True) if resume_icon else None
    if resume_link is None:
        raise RuntimeError(f"{name}人物报道页未找到“查看简历”链接")
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
    rows: list[dict] = []
    group = soup.select_one(".part04")
    duty_node = group.select_one(".lmt01") if group else None
    duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
    if not duty:
        return rows
    for link in soup.select(".part04 a"):
        name = clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
            continue
        source_url = str(page_rule.get("url", ""))
        href = str(link.get("href", ""))
        detail_url = urljoin(final_url or source_url, href) if href and not href.startswith(("#", "javascript:")) else ""
        if detail_url.rstrip("/") == source_url.rstrip("/"):
            detail_url = ""
        if not detail_url:
            raise RuntimeError(f"{name}缺少可验证的个人详情页链接")
        duty, detail_url = extract_current_duty(detail_url, name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": detail_url,
            "evidence": duty,
            "selector_summary": "新华网第二十届中央领导机构part04分组",
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
