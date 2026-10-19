from __future__ import annotations

import sys
from pathlib import Path
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2704',
 'domain': 'www.tj.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_tianjin_gov_leader_list_groups_v1',
 'leader_region_selector': 'ul.leader-list li',
 'name_selector': 'a',
 'duty_selector': '.l-sn, a.leader-img p',
 'detail_link_selector': 'ul.leader-list a[href*="/szfld/"], ul.leader-list a[href^="./szfld/"]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'ul.leader-list li',
                     'name_selector': 'a',
                     'duty_selector': '.l-sn, a.leader-img p',
                     'detail_link_selector': 'ul.leader-list a[href*="/szfld/"], ul.leader-list a[href^="./szfld/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'verified_online_page', 'verified_status': 'verified', 'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    return " ".join(value.replace("\u3000", " ").replace("\u2003", " ").split())


def _clean_name(value: str) -> str:
    name = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", _clean_text(value))
    return re.sub(r"（兼）$", "", name)


def _detail_url(base_url: str, href: str) -> str:
    value = str(href or "").strip()
    if not value or value.startswith(("#", "javascript:")) or "#" in value:
        return ""
    return urljoin(base_url, value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析天津市人民政府政务公开页市政府领导分组列表。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    top_link = soup.select_one("ul.leader-list a.leader-img[href]")
    if top_link:
        text = _clean_text(top_link.get_text(" ", strip=True))
        match = re.match(r"(?P<duty>市长)\s*(?P<name>[\u4e00-\u9fff\s]{2,8})$", text)
        if match:
            name = _clean_name(match.group("name"))
            duty = _clean_text(match.group("duty"))
            detail_url = _detail_url(final_url, top_link.get("href", ""))
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "source_url": final_url,
                    "parser": page_rule.get("parser", ""),
                    "selector_summary": "strategy=css；leader=ul.leader-list；name=group links；duty=group label；detail=a[href*=szfld]；api_enabled=False",
                }
            )
            seen.add((name, duty, detail_url))

    for item in soup.select("ul.leader-list li.h-leader"):
        duty_node = item.select_one(".l-sn")
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not duty:
            continue
        for link in item.select(".r-rm a[href]"):
            name = _clean_name(link.get_text(" ", strip=True))
            if not name:
                continue
            detail_url = _detail_url(final_url, link.get("href", ""))
            key = (name, duty, detail_url)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
                    "source_url": final_url,
                    "parser": page_rule.get("parser", ""),
                    "selector_summary": "strategy=css；leader=ul.leader-list；name=group links；duty=group label；detail=a[href*=szfld]；api_enabled=False",
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
