from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1074',
 'domain': 'www.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': 'iframe嵌入',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_hunan_gov_office_leader_blocks_v1',
 'leader_region_selector': '.wj_zzf_left .wj_lead_rw',
 'name_selector': '.wj_lead_name a',
 'duty_selector': '.wj_lead_xq a',
 'detail_link_selector': '.wj_lead_name a',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.wj_zzf_left .wj_lead_rw',
                     'name_selector': '.wj_lead_name a',
                     'duty_selector': '.wj_lead_xq a',
                     'detail_link_selector': '.wj_lead_name a',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线浏览器 DOM 中定位 iframe 领导简介列表'}}}


def clean_text(text: str) -> str:
    return " ".join(text.replace("\u3000", " ").split()).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for item in soup.select(".wj_zzf_left .wj_lead_rw"):
        name_link = item.select_one(".wj_lead_name a")
        duty_link = item.select_one(".wj_lead_xq a")
        name = clean_text(name_link.get_text(" ", strip=True)) if name_link else ""
        duty = clean_text(duty_link.get_text(" ", strip=True)) if duty_link else ""
        duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty)
        if not name or not duty:
            continue
        href = str(name_link.get("href", "")).strip() if name_link else ""
        detail_url = urljoin(final_url, href) if href else ""
        parsed_detail = urlparse(detail_url)
        if (
            not href
            or href.startswith(('#', 'javascript:'))
            or parsed_detail.netloc.lower() != urlparse(final_url).netloc.lower()
            or urldefrag(detail_url)[0].rstrip('/') == urldefrag(final_url)[0].rstrip('/')
            or not parsed_detail.path.lower().endswith(('.shtml', '.html', '.htm'))
        ):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "selector_summary": ".wj_zzf_left .wj_lead_rw 姓名链接+职务链接",
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
