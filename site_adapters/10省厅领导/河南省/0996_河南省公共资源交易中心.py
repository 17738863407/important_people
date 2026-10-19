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

PAGE_RULE = {'rule_id': '0996',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'force_browser': True,
 'extract_mode': 'custom',
 'collector': 'browser_dom',
 'parser': 'custom_henan_public_resource_detail_links_v2',
 'leader_region_selector': '.text-l li.about2 a[href]',
 'name_selector': 'a strong',
 'duty_selector': '详情页.text-r-content机构全称与姓名之间文本',
 'detail_link_selector': '.text-l li.about2 a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'playwright',
                     'detail_link_selector': '.text-l li.about2 a[href]',
                     'max_detail_links': 50},
 'risk_flag': '入口只展开首人正文；必须按左侧标签DOM顺序逐页浏览器渲染详情，并限定.text-r-content提取机构全称与姓名之间的职务',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.text-l li.about2 a[href]',
                     'name_selector': 'a strong',
                     'duty_selector': '详情页.text-r-content机构全称与姓名之间文本',
                     'detail_link_selector': '.text-l li.about2 a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '详情页 DOM 已包含职务姓名句'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'verified',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按左侧人物标签原序在线读取各自详情页职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen_names: set[str] = set()
    organization = str(page_rule.get("organization") or "")
    source_url = final_url or str(page_rule.get("url") or "")
    for link in soup.select(".text-l li.about2 a[href]"):
        name = clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            raise RuntimeError(f"领导标签姓名格式异常：{name or '<空>'}")
        if name in seen_names:
            continue
        seen_names.add(name)
        detail_url = urljoin(source_url, str(link.get("href") or ""))
        detail_result = fetch_html_with_strategy(detail_url, strategy="playwright", timeout=60)
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        content = detail_soup.select_one(".text-r-content")
        if content is None:
            raise RuntimeError(f"{name} 详情页缺少 .text-r-content")
        detail_text = clean_text(content.get_text(" ", strip=True))
        duty_match = re.search(
            re.escape(organization) + r"(?P<duty>.+?)" + re.escape(name) + r"[。.]?",
            detail_text,
        )
        if duty_match is None:
            raise RuntimeError(f"{name} 详情页未找到机构全称与姓名之间的职务")
        duty = clean_text(duty_match.group("duty")).strip("。.")
        if not duty:
            raise RuntimeError(f"{name} 详情页职务为空")
        rows.append(
            {
                "name": name,
                "duty": f"{organization}{duty}",
                "detail_url": detail_result.final_url or detail_url,
                "evidence": f"{organization}{duty}",
                "parser": "custom_henan_public_resource_detail_links_v2",
                "selector_summary": ".text-l li.about2 a[href]；详情页.text-r-content机构全称与姓名之间职务",
            }
        )
    if not rows:
        raise RuntimeError("领导介绍页未解析出左侧人物标签")
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
