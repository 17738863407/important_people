from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1010',
 'domain': 'hrss.ah.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_anhui_hrss_table_title_v1',
 'leader_region_selector': 'table.xxgk-table-list',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.xxgk_body.wza-container:nth-of-type(1) > '
                                               'div.gknews.wza-region_main:nth-of-type(2) > div.container > '
                                               'div.gk_container.bg:nth-of-type(2) > div.xxgk_lmbox.clearfix > '
                                               'div.fl.xxgk_left:nth-of-type(1) > div.xxgk_lmlink > '
                                               'div.xxgktreecon.childCont:nth-of-type(6)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '浏览器 DOM 表格标题已包含姓名和职务'}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    source_url = final_url or str(page_rule.get("url", ""))
    for link in soup.select("table.xxgk-table-list a.title[href]"):
        title = link.get("title") or link.get_text(" ", strip=True)
        if "：" not in title and ":" not in title:
            continue
        name_text, duty_text = re.split(r"[：:]", title, maxsplit=1)
        name = clean_text(name_text)
        duty = re.sub(r"\s+", "", duty_text.replace("\u3000", " ")).strip()
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duty:
            continue
        href = str(link.get("href") or "").strip()
        detail_url = ""
        if href and not href.lower().startswith(("#", "javascript:")):
            candidate_url = urljoin(source_url, href)
            if candidate_url.rstrip("/") != source_url.rstrip("/"):
                detail_url = candidate_url
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "selector_summary": "xxgk-table-list链接标题姓名冒号职务",
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
