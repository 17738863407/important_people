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

PAGE_RULE = {'rule_id': '0418',
 'domain': 'district.ce.cn',
 'page_type': '人物表格页',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'ce_district_leader_parser_v1',
 'source_parser': 'table_person_parser_v1',
 'leader_region_selector': '.main .ren2, .main .TRS_Editor, .content .TRS_Editor, .trs_editor_view',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': [],
                   'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '是',
 'profile_judgement': '网页画像通过_可用于该网页后续更新',
 'filter_policy': 'strong_no_wordlist'}

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup=BeautifulSoup(html,"html.parser"); h=next((n for n in soup.select(".main .left2 h3") if "省委领导" in n.get_text(" ",strip=True)),None); region=h.find_next_sibling(class_="ren2") if h else None
    if region is None:return []
    base=final_url or str(page_rule.get("url",""));rows=[];seen=set()
    for tr in region.select("tr"):
        a=tr.select_one("a[href]");c=tr.select("td");name=re.sub(r"\s+","",a.get_text(" ",strip=True) if a else "");duty=re.sub(r"\s+"," ",c[-1].get_text(" ",strip=True) if len(c)>=2 else "").strip()
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}",name) and duty and name not in seen:seen.add(name);rows.append({"name":name,"duty":duty,"evidence":duty,"detail_url":urljoin(base,a.get("href",""))})
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
