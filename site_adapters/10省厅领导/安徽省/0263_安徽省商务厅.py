from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    """压缩 HTML 文本中的换行、全角空格、不换行空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析安徽省商务厅政府信息公开领导列表。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    source_url = final_url or str(page_rule.get("url", ""))

    org_name = str(page_rule.get("organization", ""))
    for link in soup.select(".xxgk_lmright .xxgk_nav_list li a.title[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        if org_name not in text:
            continue
        text = clean_text(text.replace(org_name, "", 1))
        match = re.match(
            r"(?P<duty>.+?(?:厅长|副厅长|巡视员|纪检监察组组长|总经济师|总会计师|总工程师))\s*(?P<name>[\u4e00-\u9fff·]{2,8})$",
            text,
        )
        if not match:
            continue

        name = clean_text(match.group("name")).replace(" ", "")
        duty = clean_text(match.group("duty"))
        if not duty:
            continue

        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)

        href = clean_text(str(link.get("href") or ""))
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
                "confidence": "high",
                "parser": "page_inline_ah_commerce_public_list_v1",
            }
        )
    return rows


PAGE_RULE = {'rule_id': '0263',
 'domain': 'commerce.ah.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_inline_ah_commerce_public_list_v1',
 'leader_region_selector': '.xxgk_lmright .xxgk_nav_list li',
 'name_selector': '.xxgk_lmright .xxgk_nav_list li a.title',
 'duty_selector': '.xxgk_lmright .xxgk_nav_list li a.title',
 'detail_link_selector': '.xxgk_lmright .xxgk_nav_list li a.title[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.xxgk_lmright .xxgk_nav_list li',
                     'name_selector': '.xxgk_lmright .xxgk_nav_list li a.title',
                     'duty_selector': '.xxgk_lmright .xxgk_nav_list li a.title',
                     'detail_link_selector': '.xxgk_lmright .xxgk_nav_list li a.title[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '当前脚本缺少可复现 api 配置，沿用在线页面定位字段'}}}


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
