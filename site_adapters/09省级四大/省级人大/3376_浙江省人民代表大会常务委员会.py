from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3376',
 'domain': 'www.zjrd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_leader_list_zhejiang_people_congress_v1',
 'leader_region_selector': '.leader_list .item_li',
 'name_selector': '.item_rigth_list span',
 'duty_selector': '.item_left_name',
 'detail_link_selector': '.item_rigth_list a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.leader_list .item_li',
                     'name_selector': '.item_rigth_list span',
                     'duty_selector': '.item_left_name',
                     'detail_link_selector': '.item_rigth_list a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析浙江省人大常委会主任之窗领导列表。"""
    organization = page_rule["organization"]
    base_url = final_url or page_rule["url"]
    parsed_url = urlsplit(base_url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": f"{parsed_url.scheme}://{parsed_url.netloc}/",
    }
    try:
        response = requests.get(base_url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
    except requests.RequestException:
        soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for group in soup.select(".leader_list .item_li"):
        duty_node = group.select_one(".item_left_name")
        duty = re.sub(r"[\s:：]+", "", duty_node.get_text("", strip=True) if duty_node else "")
        if duty not in {"主任", "副主任", "秘书长"}:
            continue
        for link in group.select(".item_rigth_list a[href]"):
            name_node = link.select_one("span")
            name = re.sub(r"\s+", "", name_node.get_text("", strip=True) if name_node else "")
            if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
                continue
            if name in seen:
                continue
            detail_url = urljoin(base_url, link.get("href", ""))
            if detail_url.rstrip("/") == base_url.rstrip("/"):
                detail_url = ""
            seen.add(name)
            rows.append(
                {
                    "organization": organization,
                    "url": page_rule["url"],
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "parser": page_rule["parser"],
                    "selector_summary": ".leader_list分组职务+卡片姓名",
                }
            )
    if rows:
        return rows

    script_text = "\n".join(script.get_text("\n", strip=False) for script in soup.select("script:not([src])"))
    leader_match = re.search(r"leaderLsit\s*:\s*\[(.*?)\]\s*,\s*mounted\s*:", script_text, re.S)
    if not leader_match:
        return rows
    for group_match in re.finditer(
        r"\{\s*title\s*:\s*['\"](?P<duty>[^'\"]+)['\"]\s*,\s*list\s*:\s*\[(?P<items>.*?)\]\s*\}",
        leader_match.group(1),
        re.S,
    ):
        duty = re.sub(r"[\s:：]+", "", group_match.group("duty"))
        if duty not in {"主任", "副主任", "秘书长"}:
            continue
        for item_match in re.finditer(
            r"\{[^{}]*?url\s*:\s*['\"](?P<url>[^'\"]+)['\"][^{}]*?name\s*:\s*['\"](?P<name>[^'\"]+)['\"][^{}]*?\}",
            group_match.group("items"),
            re.S,
        ):
            name = re.sub(r"\s+", "", item_match.group("name"))
            if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
                continue
            detail_url = urljoin(base_url, item_match.group("url"))
            if detail_url.rstrip("/") == base_url.rstrip("/"):
                detail_url = ""
            seen.add(name)
            rows.append(
                {
                    "organization": organization,
                    "url": page_rule["url"],
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "parser": page_rule["parser"],
                    "selector_summary": "同页leaderLsit职务分组+人物对象",
                }
            )
    return rows


if __name__ == "__main__":
    main()
