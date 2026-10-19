from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0106',
 'domain': 'sft.nx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_online_nx_sft_profile_paragraphs_v1',
 'leader_region_selector': '.TRS_UEDITOR p',
 'name_selector': 'paragraph before ，',
 'duty_selector': 'text after ； before 分工',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'max_detail_links': 50},
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.TRS_UEDITOR p',
                     'name_selector': 'paragraph before ，',
                     'duty_selector': 'text after ； before 分工',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面采集'}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析宁夏回族自治区司法厅领导分工正文。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(".TRS_UEDITOR p"):
        text = re.sub(r"[\s\u3000\xa0]+", "", paragraph.get_text(" ", strip=True))
        if "；自治区司法厅" not in text:
            continue
        name_match = re.match(r"^([\u4e00-\u9fff]{2,4})，", text)
        if not name_match:
            continue
        name = name_match.group(1)
        duty = text.split("；", 1)[1]
        duty = re.split(r"[，。](?:主持|负责|协助|分管)", duty, 1)[0].strip("，。；")
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".TRS_UEDITOR p 段落分号后职务",
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
