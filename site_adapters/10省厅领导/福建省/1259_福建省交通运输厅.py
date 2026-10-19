from __future__ import annotations

import sys
import re
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

PAGE_RULE = {'rule_id': '1259',
 'domain': 'jtyst.fujian.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'inline_parser_handles_fetch': True,
 'inline_fetch_collector': 'requests',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_fujian_transport_leader_detail_tup_v1',
 'leader_region_selector': '.ldzc_nav li a[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0},
 'risk_flag': '页脚全国交通系统网站等非人物链接干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.ldzc_nav li a[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用在线列表详情链接逐页解析'}}}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """姓名内部不保留排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_duty(value: str) -> str:
    """清理职务文本。"""
    duty = normalize_space(value).strip(" ：:，。")
    duty = re.sub(r"\s*、\s*", "、", duty)
    duty = re.sub(r"\s*，\s*", "，", duty)
    return duty.strip(" ，。")


def fetch_detail_html(detail_url: str, referer: str, current_html: str) -> str:
    """在线读取领导详情页。"""
    if detail_url.rstrip("/") == referer.rstrip("/"):
        return current_html
    response = requests.get(
        detail_url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": referer},
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def extract_profile_from_detail(detail_html: str) -> tuple[str, str, str]:
    """从详情页头像旁字段读取姓名和职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    values = [normalize_space(node.get_text(" ", strip=True)) for node in soup.select(".ldxx_box_right .tup p")]
    values = [value for value in values if value]
    if len(values) < 2:
        return "", "", normalize_space(soup.get_text(" ", strip=True))[:120]
    duty = clean_duty(values[0])
    name = clean_name(values[1])
    return name, duty, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析福建省交通运输厅领导导航，并在线读取详情补全职务。"""
    if not html:
        entry_url = str(page_rule["url"])
        column_match = re.search(r"^(.*?/ldzc/)", entry_url)
        if column_match is None:
            raise RuntimeError("规则入口无法定位领导之窗栏目")
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": entry_url})
        column_response = session.get(column_match.group(1), timeout=30)
        column_response.raise_for_status()
        column_soup = BeautifulSoup(column_response.text, "html.parser")
        refresh = column_soup.select_one('meta[http-equiv="refresh"][content]')
        refresh_match = re.search(
            r"url\s*=\s*([^;]+)",
            str(refresh.get("content") if refresh else ""),
            flags=re.IGNORECASE,
        )
        if refresh_match is None:
            raise RuntimeError("领导之窗栏目未发现当前人物页跳转")
        current_response = session.get(
            urljoin(column_response.url, refresh_match.group(1).strip(" \"'")), timeout=30
        )
        current_response.raise_for_status()
        current_response.encoding = "utf-8"
        html = current_response.text
        final_url = current_response.url

    soup = BeautifulSoup(html, "html.parser")
    page_url = str(page_rule.get("url", "")) or final_url
    base_url = final_url or page_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = "strategy=custom_parse_page；selector=.ldzc_nav li a[href]；detail=online；field=.tup p"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".ldzc_nav li a[href]"):
        href = str(link.get("href") or "").strip()
        if not href or href.lower().startswith(("#", "javascript:")):
            continue
        detail_url = urljoin(base_url, href)
        if detail_url in seen:
            continue
        try:
            detail_html = fetch_detail_html(detail_url, base_url, html)
        except requests.RequestException:
            continue
        name, duty, evidence = extract_profile_from_detail(detail_html)
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duty:
            continue
        seen.add(detail_url)
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
