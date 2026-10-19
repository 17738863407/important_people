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

PAGE_RULE = {'rule_id': '1429',
 'domain': 'www.lnrd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_liaoning_rd_grouped_jgtop_members_v1',
 'leader_region_selector': 'ul.JGTop',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'ul.JGTop a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '组成人员按JGTop职务分组，旧body解析全为导航污染；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'ul.JGTop',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'ul.JGTop a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'behavior_changed': True}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"[（(].*?[）)]", "", text)
    return re.sub(r"\s+", "", text)


def clean_duty(value: str) -> str:
    return clean_text(value).replace(" ", "")


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(rule.get("url", ""))
    rows = []
    seen = set()
    for group in soup.select("ul.JGTop"):
        duty_node = group.select_one("h4")
        if not duty_node:
            continue
        duty = clean_duty(duty_node.get_text(" ", strip=True))
        if duty not in {"主任", "主任委员", "副主任", "副主任委员", "秘书长"}:
            continue
        for link in group.select("a"):
            raw_name = clean_text(link.get_text(" ", strip=True))
            name = clean_name(raw_name)
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
                continue
            href = link.get("href", "")
            detail_url = urljoin(base_url, href) if href else ""
            key = (name, duty)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "organization": str(rule.get("organization", "")),
                    "url": base_url,
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": duty,
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
