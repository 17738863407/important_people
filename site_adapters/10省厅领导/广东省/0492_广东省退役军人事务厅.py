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

PAGE_RULE = {'rule_id': '0492',
 'domain': 'dva.gd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_online_gddva_detail_profile_v1',
 'leader_region_selector': 'div.content-container:nth-of-type(2)',
 'name_selector': 'a.document-number',
 'duty_selector': '.article-content',
 'detail_link_selector': 'a.document-number',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'max_detail_links': 50},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div.content-container:nth-of-type(2)',
                     'name_selector': 'a.document-number',
                     'duty_selector': '.article-content',
                     'detail_link_selector': 'a.document-number',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线浏览器 DOM 名单与在线详情页逐页解析'}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析广东省退役军人事务厅在线领导名单及详情页。"""
    def clean(text: str) -> str:
        return re.sub(r"[\s\u3000\xa0]+", "", text)

    parser = str(page_rule.get("parser", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.select("a.document-number[href]"):
        name = clean(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, link.get("href") or "")
        duty = ""
        evidence = ""
        try:
            response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0", "Referer": final_url}, timeout=20)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            detail_soup = BeautifulSoup(response.text, "html.parser")
            content = detail_soup.select_one(".article-content")
            text = clean(content.get_text(" ", strip=True) if content else "")
            match = re.search(r"现任(?:广东省|省)?退役军人事务厅[^。]*。", text)
            if match:
                duty = match.group(0).removeprefix("现任").rstrip("。")
                evidence = duty
        except requests.RequestException:
            pass
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": parser,
                "selector_summary": "列表a.document-number可见姓名+在线详情.article-content现任句",
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
