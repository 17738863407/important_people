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

PAGE_RULE = {'rule_id': '2341',
 'domain': 'sft.xizang.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_to_detail',
 'collector': 'static_http',
 'parser': 'V011_directory_link_v1',
 'leader_region_selector': 'html > body > div.centerWidth:nth-of-type(3) > '
                           'div.nxz-overview.nxz-overview-gl:nth-of-type(2) > div.row.cont:nth-of-type(2) > '
                           'div.vxz-leader-jlbox.mt20:nth-of-type(5)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'detail_chain',
 'locator': {'css': {'leader_region_selector': 'html > body > div.centerWidth:nth-of-type(3) > '
                                               'div.nxz-overview.nxz-overview-gl:nth-of-type(2) > '
                                               'div.row.cont:nth-of-type(2) > div.vxz-leader-jlbox.mt20:nth-of-type(5)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': False}}}


def clean_text(text: str) -> str:
    """压缩网页文本空白。"""
    return re.sub(r"[\s\u00A0\u3000]+", " ", str(text or "")).strip()


def clean_name(text: str) -> str:
    """清理姓名字段。"""
    return re.sub(r"[\s\u00A0\u3000]+", "", str(text or "")).strip(" ，,。；;")


def clean_duty(text: str) -> str:
    """清理“现任”后的职务文本。"""
    duty = clean_text(text).strip(" ：:，,。；;")
    return duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析西藏自治区司法厅领导介绍卡片，避免详情链误抽姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for box in soup.select(".vxz-leader-jlbox"):
        text = clean_text(box.get_text(" ", strip=True))
        match = re.search(r"^(.+?)[，,]\s*现任(.+?)[。.]?$", text)
        if not match:
            continue
        name = clean_name(match.group(1))
        duty = clean_duty(match.group(2))
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        link = box.select_one("a[href]")
        detail_url = urljoin(final_url or source_url, link.get("href", "")) if link else ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_xizang_justice_card_v1",
                "selector_summary": ".vxz-leader-jlbox；text=姓名，现任职务",
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
