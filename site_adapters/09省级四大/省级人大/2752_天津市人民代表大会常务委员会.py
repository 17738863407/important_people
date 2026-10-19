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

PAGE_RULE = {'rule_id': '2752',
 'domain': 'www.tjrd.gov.cn',
 'page_type': '人物表格页',
 'structure_group': 'problem_table_compound_person',
 'reuse_scope': 'page_structure',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_tianjin_rd_weiruan16_leader_table_v1',
 'leader_region_selector': 'td.weiruan16:has(span.yansehui strong):has(a[href])',
 'name_selector': 'a[href]',
 'duty_selector': 'span.yansehui strong',
 'detail_link_selector': 'td.weiruan16 a[href]',
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
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'td.weiruan16:has(span.yansehui strong):has(a[href])',
                     'name_selector': 'a[href]',
                     'duty_selector': 'span.yansehui strong',
                     'detail_link_selector': 'td.weiruan16 a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'verified', 'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    text = " ".join(value.split())
    text = text.replace("\u3000", "")
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return text.strip(" ｜|")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析天津市人大常委会领导之窗右侧职务表。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for cell in soup.select("td.weiruan16:has(span.yansehui strong):has(a[href])"):
        duties = [_clean_text(node.get_text(" ", strip=True)) for node in cell.select("span.yansehui strong")]
        links = [node for node in cell.select("a[href]")]
        for duty, link in zip(duties, links):
            name = _clean_text(link.get_text(" ", strip=True))
            detail_url = urljoin(final_url, link.get("href", "").strip())
            if detail_url.rstrip("/") == final_url.rstrip("/"):
                detail_url = ""
            if not name or not duty:
                continue
            key = (name, duty, detail_url)
            if key in seen:
                continue
            seen.add(key)
            evidence = duty
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": detail_url,
                    "evidence": evidence,
                    "source_url": final_url,
                    "parser": page_rule.get("parser", ""),
                    "selector_summary": "strategy=css；leader=td.weiruan16:has(span.yansehui strong):has(a[href])；name=a[href]；duty=span.yansehui strong；detail=td.weiruan16 a[href]；api_enabled=False",
                }
            )
    return records


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
