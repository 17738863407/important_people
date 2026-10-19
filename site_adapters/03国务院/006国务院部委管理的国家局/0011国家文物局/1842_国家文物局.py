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

PAGE_RULE = {'rule_id': '1842',
 'domain': 'www.ncha.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': 'iframe嵌入',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'online_ncha_leader_table_v1',
 'leader_region_selector': 'table:has(a[href*=\"art_1737\"])',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '新闻人物或正文干扰；页面包含iframe',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'table a[href*=\"art_1737\"]',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线渲染页面包含领导简介表格数据'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    """压缩网页空白，保留职务与姓名之间的语义分隔。"""
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """解析国家文物局领导简介表格中的详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    grouped_links: dict[str, list[str]] = {}
    for link in soup.select('a[href*="art_1737"]'):
        href = link.get("href", "")
        text = clean_text(link.get_text(" ", strip=True))
        if not href or not text:
            continue
        full_url = urljoin(final_url or page_rule["url"], href)
        grouped_links.setdefault(full_url, [])
        if text not in grouped_links[full_url]:
            grouped_links[full_url].append(text)

    rows: list[dict] = []
    seen_names: set[str] = set()
    for detail_url, texts in grouped_links.items():
        duty = ""
        name = ""
        if len(texts) >= 2 and re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", texts[-1]):
            name = texts[-1]
            duty = clean_text(" ".join(texts[:-1]))
        else:
            text = texts[0]
            match = re.match(r"(.+?)\s+([\u4e00-\u9fa5]{2,4})$", text)
            if match:
                duty = clean_text(match.group(1))
                name = match.group(2)
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "detail_url": detail_url,
            "evidence": duty,
            "selector_summary": "领导简介表格art_1737链接按详情页分组解析",
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
