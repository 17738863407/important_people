from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")



PAGE_RULE = {'rule_id': '1205',
 'domain': 'jshrss.jiangsu.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_jiangsu_hrss_online_detail_xianren_v2',
 'leader_region_selector': '#325904 .content_box_list li a[href]',
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
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '#325904 .content_box_list li a[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """姓名内部不保留排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_duty(value: str) -> str:
    """清理“现任”后面的机构前缀和句末标点。"""
    duty = normalize_space(value).rstrip("。")
    duty = re.sub(r"\s*、\s*", "、", duty)
    duty = re.sub(r"^江苏省人力资源和社会保障厅", "", duty)
    duty = re.sub(r"^省人力资源和社会保障厅", "", duty)
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


def extract_duty_from_detail(detail_html: str, name: str) -> tuple[str, str]:
    """从详情页正文第一段“现任……”句提取职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one("#Zoom") or soup.select_one(".text")
    if not content:
        return "", ""
    for para in content.select("p"):
        text = normalize_space(para.get_text(" ", strip=True))
        if name not in text or "现任" not in text:
            continue
        match = re.search(r"现任(.+?)(?:。|$)", text)
        if not match:
            continue
        evidence = normalize_space(match.group(1)).rstrip("。").strip()
        evidence = re.sub(r"\s*、\s*", "、", evidence)
        return clean_duty(match.group(1)), evidence
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析江苏省人社厅领导分工列表，并在线读取详情页补全职务。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    page_url = str(page_rule.get("url", "")) or final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = (
        "strategy=custom_parse_page；selector=find(id='325904') script CDATA record li a[href]；"
        "detail=online detail page；field=#Zoom p contains 现任"
    )
    box = soup.find(id="325904")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    record_html_list = re.findall(r"<record><!\[CDATA\[(.*?)\]\]></record>", str(box or ""), flags=re.S)
    links = []
    for record_html in record_html_list:
        record_soup = BeautifulSoup(record_html, "html.parser")
        links.extend(record_soup.select("li a[href]"))

    for link in links:
        title = link.select_one(".list_title")
        listed_name = clean_name(title.get_text(" ", strip=True) if title else link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", listed_name) or listed_name == "领导分工" or listed_name in seen:
            continue
        detail_url = urljoin(page_url, link.get("href", ""))
        parsed_detail = urlparse(detail_url)
        parsed_source = urlparse(page_url)
        if (
            parsed_detail.scheme not in {"http", "https"}
            or parsed_detail.netloc.lower() != parsed_source.netloc.lower()
            or parsed_detail.path.rstrip("/") == parsed_source.path.rstrip("/")
            or parsed_detail.fragment
        ):
            continue
        duty, evidence_text = extract_duty_from_detail(load_detail_html(detail_url, page_url), listed_name)
        if not duty:
            continue
        seen.add(listed_name)
        rows.append(
            {
                "organization": organization,
                "url": page_url,
                "name": listed_name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence_text,
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
