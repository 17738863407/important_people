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



PAGE_RULE = {'rule_id': '1221',
 'domain': 'jt.guizhou.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'detail_follow',
 'collector': 'static_http',
 'parser': 'page_guizhou_transport_online_leader_sections_v2',
 'leader_region_selector': '.zfxxgk_zdgktit + .zfxxgk_zdgkc a[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '旧规则选择器为空且允许最多 50 个详情链接，容易回退扫描整页政务公开导航并产生超长候选参数；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.zfxxgk_zdgktit + .zfxxgk_zdgkc a[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """姓名内部不保留排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_duty(value: str) -> str:
    """统一职务文本标点与空白。"""
    duty = normalize_space(value).strip(" ，。")
    duty = re.sub(r"\s*、\s*", "、", duty)
    duty = re.sub(r"\s*，\s*", "，", duty)
    return duty


def load_detail_html(detail_url: str, referer: str) -> str:
    """在线获取领导详情页 HTML。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer,
    }
    session = requests.Session()
    session.trust_env = False
    response = session.get(detail_url, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text


def extract_standard_detail(detail_html: str) -> tuple[str, str, str]:
    """机构领导详情页使用 h3 和 p.drzz 分别承载姓名、职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    info = soup.select_one(".ldinfo") or soup
    name_tag = info.select_one("h3")
    duty_tag = info.select_one("p.drzz")
    name = clean_name(name_tag.get_text(" ", strip=True)) if name_tag else ""
    duty = clean_duty(duty_tag.get_text(" ", strip=True)) if duty_tag else ""
    return name, duty, duty


def extract_named_duty_detail(detail_html: str) -> tuple[str, str, str]:
    """总工程师等详情页正文包含“姓名：... 职务：...”字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one(".TRS_UEDITOR") or soup.select_one(".ldinfo") or soup
    text = normalize_space(content.get_text(" ", strip=True))
    match = re.search(r"姓名[:：]\s*(?P<name>[\u4e00-\u9fa5]{2,4})\s*职务[:：]\s*(?P<duty>.+?)(?:\s+负责|办公时间|$)", text)
    if not match:
        return "", "", ""
    duty = clean_duty(match.group("duty"))
    return clean_name(match.group("name")), duty, duty


def find_following_content(title_tag):
    """找到标题后紧邻的领导链接容器。"""
    node = title_tag.find_next_sibling()
    while node is not None:
        classes = node.get("class", []) if getattr(node, "get", None) else []
        if "zfxxgk_zdgkc" in classes:
            return node
        node = node.find_next_sibling()
    return None


def append_row(
    rows: list[dict[str, str]],
    seen: set[str],
    parser: str,
    selector_summary: str,
    name: str,
    duty: str,
    detail_url: str,
    evidence: str,
) -> None:
    """追加一条去重后的领导记录。"""
    if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duty or name in seen:
        return
    seen.add(name)
    rows.append(
        {
            "name": name,
            "duty": duty,
            "detail_url": detail_url,
            "evidence": evidence or f"{name}：{duty}",
            "parser": parser,
            "selector_summary": selector_summary,
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析贵州省交通运输厅领导分区，并在线读取详情页补全姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    page_url = str(page_rule.get("url", "")) or final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = (
        "strategy=custom_parse_page；section=.zfxxgk_zdgktit + .zfxxgk_zdgkc；"
        "detail=online detail page；field=.ldinfo h3+p.drzz 或 .TRS_UEDITOR 姓名/职务"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for title_tag in soup.select(".zfxxgk_zdgktit"):
        title = normalize_space(title_tag.get_text(" ", strip=True))
        if title not in {"机构领导", "总工程师、总规划师、安全总监"}:
            continue
        content = find_following_content(title_tag)
        if not content:
            continue
        for link in content.select("a[href]"):
            detail_url = urljoin(page_url, link.get("href", ""))
            detail_html = load_detail_html(detail_url, page_url)
            if title == "机构领导":
                name, duty, evidence = extract_standard_detail(detail_html)
            else:
                name, duty, evidence = extract_named_duty_detail(detail_html)
            append_row(rows, seen, parser, selector_summary, name, duty, detail_url, evidence)
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
