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

PAGE_RULE = {'rule_id': '2489',
 'domain': 'slt.hebei.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'list_detail_online_hebei_water_leaders_v1',
 'leader_region_selector': '领导专区姓名列表',
 'name_selector': '列表页领导姓名链接',
 'duty_selector': '详情页打印后职责分工前职务',
 'detail_link_selector': '领导姓名详情链接',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"static_http","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '缺少稳定领导区域选择器',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面直接提供领导列表及详情信息'}}}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u00a0\u3000]+", " ", value).strip()
    return re.sub(r"\s*([、，,。；;（）()])\s*", r"\1", text)


def _extract_duty(detail_html: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    segment = text.split("打印", 1)[-1]
    for marker in ("负责", "主持", "分管", "机构设置"):
        if marker in segment:
            segment = segment.split(marker, 1)[0]
    return _clean_text(segment).rstrip("，,。；;")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析河北省水利厅领导列表，并在线获取详情职务。"""
    page_url = str(page_rule.get("url", "")) or final_url
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145 Safari/537.36",
               "Referer": "http://slt.hebei.gov.cn/"}
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select(".item_lst li a[href]"):
        response = requests.get(page_url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".item_lst li a[href]"):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        detail_url = urljoin(page_url, str(link.get("href") or ""))
        detail_response = requests.get(detail_url, headers=headers, timeout=30)
        detail_response.raise_for_status()
        detail_response.encoding = detail_response.apparent_encoding or "utf-8"
        duty = _extract_duty(detail_response.text)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule["parser"]),
                "selector_summary": "列表页姓名链接+详情页打印后职务",
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
