from __future__ import annotations

import re
import sys
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

PAGE_RULE = {'rule_id': '0781',
 'domain': 'gxt.gxzf.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'page_inline_guangxi_gxt_leader_list_detail_present_sentence_v1',
 'leader_region_selector': '.gov-leader-list a[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.gov-leader-list a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '原详情链抽到页面打印按钮导致“打印XXX”重复，并漏掉袁煌；需限定领导列表',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.gov-leader-list a[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.gov-leader-list a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'}}}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def load_detail_html(name: str, detail_url: str, referer: str) -> str:
    """在线获取详情页 HTML。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": referer,
    }
    session = requests.Session()
    session.trust_env = False
    response = session.get(detail_url, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_detail_duty(detail_html: str) -> tuple[str, str]:
    """从详情页“现任……”句提取职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one(".trs_editor_view") or soup.select_one(".TRS_UEDITOR")
    text = clean_text((content or soup).get_text(" ", strip=True))
    match = re.search(r"现任(?P<duty>[^。]+?)。", text)
    if not match:
        match = re.search(r"现任(?P<duty>.+?)(?=负责|分工|$)", text)
    if not match:
        return "", ""
    duty = clean_text(match.group("duty")).rstrip("。；")
    return duty, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析广西壮族自治区工业和信息化厅领导列表及详情页职务。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".gov-leader-list a[href]"):
        span = link.select_one("span")
        name = clean_text((span or link).get_text(" ", strip=True)).replace(" ", "")
        href = str(link.get("href") or "")
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not href:
            continue
        detail_url = urljoin(source_url, href)
        duty, evidence = parse_detail_duty(load_detail_html(name, detail_url, source_url))
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".gov-leader-list取姓名和详情链接；详情页现任句提取职务",
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
