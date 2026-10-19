from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0993',
 'domain': 'hnga.henan.gov.cn',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_henan_police_limited_detail_v1',
 'leader_region_selector': 'li.cl a[href]',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '原广义详情解析将责任编辑李明和新闻/页脚文本误抽为领导；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'li.cl a[href]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录页限定机构领导姓名链接，详情页只截取分享到责任编辑之间的职务正文'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩详情页正文空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """去除姓名中的排版空格。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_status_markers(value: str) -> str:
    """仅删除无期限独立状态标记，保留职级及带期限挂职信息。"""
    marker = r"(?:（(?:兼|挂职|主持日常工作|主持工作)）|\((?:兼|挂职|主持日常工作|主持工作)\)|[<＜](?:兼|挂职)[>＞])"
    return re.sub(marker, "", clean_text(value)).strip("，。；;、 ")


def fetch_detail_text(url: str) -> str:
    """读取领导详情页文本，强制按 UTF-8 解码避免 requests 误判 ISO-8859-1。"""
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        html = response.read().decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    return clean_text(soup.get_text(" ", strip=True))


def extract_duty(detail_text: str, name: str) -> str:
    """从详情页元信息之后截取职务，排除责任编辑和页脚。"""
    pattern = rf"{re.escape(name)}\s*时间：.*?分享：\s*(.+?)\s*责任编辑："
    match = re.search(pattern, detail_text)
    if not match:
        match = re.search(r"分享：\s*(.+?)\s*责任编辑：", detail_text)
    if not match:
        return ""
    return clean_text(match.group(1)).strip("，。；;、 ")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析河南省公安厅机构领导目录，并受限读取对应详情页职务。"""
    soup = BeautifulSoup(html, "html.parser")
    page_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；selector=li.cl a[title]；detail_boundary=分享到责任编辑"

    for link in soup.select("li.cl a[href][title]"):
        name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
            continue
        detail_url = urljoin(page_url, str(link.get("href", "")))
        if name in seen:
            continue
        seen.add(name)
        try:
            detail_text = fetch_detail_text(detail_url)
            duty = clean_status_markers(extract_duty(detail_text, name))
        except Exception:
            continue
        if not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "order": len(rows) + 1,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
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
