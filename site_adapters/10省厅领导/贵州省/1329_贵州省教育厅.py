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

PAGE_RULE = {'rule_id': '1329',
 'domain': 'jyt.guizhou.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_guizhou_edu_ldzc_detail_fields_v1',
 'leader_region_selector': '.ldzc li a[href^="http"][href*="/ldzc/"]',
 'name_selector': '.name',
 'duty_selector': '.zw',
 'detail_link_selector': '.ldzc li a[href^="http"][href*="/ldzc/"]',
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
 'risk_flag': '列表页左侧多人姓名，详情页.name/.zw字段补职务；旧body字段解析仅取默认首人；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.ldzc li a[href^="http"][href*="/ldzc/"]',
                     'name_selector': '.name',
                     'duty_selector': '.zw',
                     'detail_link_selector': '.ldzc li a[href^="http"][href*="/ldzc/"]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def fetch_detail_html(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_detail_fields(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.select_one(".name")
    duty_nodes = soup.select(".zw")
    if not name_node or not duty_nodes:
        return "", "", ""
    name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
    duty = clean_text(duty_nodes[0].get_text(" ", strip=True))
    duty = re.sub(r"[（(]\s*挂职\s*[）)]", "", duty)
    if not re.search(r"书记|厅长|成员|督学|主任|巡视员|专员|副主委|干部|主席", duty):
        return "", "", ""
    return name, duty, duty


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = str(rule.get("url", "")) or final_url
    rows = []
    seen = set()
    for link in soup.select('.ldzc li a[href^="http"][href*="/ldzc/"]'):
        list_name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", list_name):
            continue
        detail_url = urljoin(base_url, link.get("href", ""))
        try:
            name, duty, evidence = extract_detail_fields(fetch_detail_html(detail_url))
        except Exception:
            continue
        name = name or list_name
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": str(rule.get("parser", "")),
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
