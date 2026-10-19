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

PAGE_RULE = {'rule_id': '2338',
 'domain': 'sft.shaanxi.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'V004_card_person_v1',
 'leader_region_selector': 'html > body > div.ldxq:nth-of-type(4)',
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
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；页面包含iframe',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.ldxq:nth-of-type(4)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'}}}


def clean_name(text: str) -> str:
    """清理姓名中的普通空格和全角空格。"""
    return re.sub(r"[\s\u00A0\u3000]+", "", str(text or "")).strip()


def clean_duty(text: str) -> str:
    """清理职务并去掉当前机构名前缀。"""
    duty = re.sub(r"[\s\u00A0\u3000]+", "", str(text or "")).strip(" ：:，,。；;")
    if duty.startswith("陕西省司法厅"):
        duty = duty[len("陕西省司法厅"):].strip(" ：:，,。；;")
    return duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析陕西省司法厅领导信息菜单，排除新闻列表链接干扰。"""
    soup = BeautifulSoup(html, "html.parser")
    content_url = final_url
    if not soup.select_one("div.ldxq a[href]"):
        refresh = soup.select_one('meta[http-equiv="Refresh"], meta[http-equiv="refresh"]')
        refresh_content = str(refresh.get("content") or "") if refresh else ""
        refresh_match = re.search(r"URL\s*=\s*(?P<href>.+)$", refresh_content, flags=re.I)
        if refresh_match:
            content_url = urljoin(final_url, refresh_match.group("href").strip(" '\""))
            response = requests.get(
                content_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
            content_url = response.url
            soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("div.ldxq a[href]"):
        name_node = link.select_one(".name")
        duty_node = link.select_one(".status")
        if not name_node or not duty_node:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        duty = clean_duty(duty_node.get_text(" ", strip=True))
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(content_url, link.get("href", ""))
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": detail_url,
                "evidence": re.sub(r"(?:（兼）|\(兼\)|[<＜]兼[>＞])", "", re.sub(r"\s+", " ", duty_node.get_text(" ", strip=True))).strip(" ，、；"),
                "parser": "custom_shaanxi_justice_menu_v1",
                "selector_summary": "div.ldxq a[href]；name=.name；duty=.status",
                "order": str(len(rows) + 1),
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
