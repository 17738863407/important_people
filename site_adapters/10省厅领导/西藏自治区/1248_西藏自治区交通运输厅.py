from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1248',
 'domain': 'jtt.xizang.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_xizang_transport_leader_detail_job_v1',
 'leader_region_selector': 'a[href*="/jggk/ldjs/"][href$=".html"], a[href^="./"][href$=".html"]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '旧规则候选链接混入权责清单、政策文件等栏目链接，且最多允许 50 个详情链接，容易把栏目正文误作人物信息；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'a[href*="/jggk/ldjs/"][href$=".html"], a[href^="./"][href$=".html"]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'pending_root', 'behavior_changed': True}}}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """姓名内部不保留排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_duty(value: str) -> str:
    """清理职务文本。"""
    duty = normalize_space(value).strip(" ：:，。")
    for prefix in ("西藏自治区交通运输厅", "自治区交通运输厅", "区交通运输厅"):
        if duty.startswith(prefix):
            duty = duty[len(prefix):]
    duty = re.sub(r"\s*、\s*", "、", duty)
    duty = re.sub(r"\s*，\s*", "，", duty)
    return duty.strip(" ，。")


def read_detail_html(detail_url: str) -> str:
    """在线读取当前人物详情页。"""
    response = requests.get(detail_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def extract_duty_from_detail(detail_html: str) -> tuple[str, str]:
    """从详情页固定的 job 字段中读取职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    job_node = soup.select_one("p.job")
    if job_node:
        evidence = normalize_space(job_node.get_text(" ", strip=True))
        return clean_duty(evidence), evidence
    text = normalize_space(soup.get_text(" ", strip=True))
    match = re.search(r"现任(?P<duty>[^。]{2,100})。", text)
    if not match:
        return "", text[:120]
    return clean_duty(match.group("duty")), match.group(0)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析西藏自治区交通运输厅领导目录，并在线读取详情补全职务。"""
    soup = BeautifulSoup(html, "html.parser")
    page_url = final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = "strategy=custom_parse_page；selector=ldjs/*.html 姓名链接；detail=online；field=p.job"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="/jggk/ldjs/"][href$=".html"], a[href^="./"][href$=".html"]'):
        name = clean_name(link.get_text(" ", strip=True))
        href = link.get("href", "")
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or "t" not in href or name in seen:
            continue
        detail_url = urljoin(page_url, href)
        try:
            duty, evidence = extract_duty_from_detail(read_detail_html(detail_url))
        except requests.RequestException:
            continue
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": parser,
                "selector_summary": selector_summary,
            }
        )
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
