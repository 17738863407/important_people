from __future__ import annotations

import sys
from pathlib import Path
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0128',
 'domain': 'www.cae.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': 'iframe嵌入',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'V011_directory_link_v1',
 'leader_region_selector': 'html > body > div.mdbg:nth-of-type(4) > div.mdbgline > div.right_md:nth-of-type(2) > '
                           'div.right_block > div.right_md_yld:nth-of-type(2)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；页面包含iframe；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'html > body > div.mdbg:nth-of-type(4) > div.mdbgline > '
                                               'div.right_md:nth-of-type(2) > div.right_block > '
                                               'div.right_md_yld:nth-of-type(2)',
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


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析中国工程院院领导合并页，标题格式为“职务-姓名”。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url") or "")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for title_node in soup.select(".right_md_yld .yld_bluetop"):
        text = re.sub(r"\s+", "", title_node.get_text("", strip=True))
        match = re.match(r"^(?P<duty>院长|副院长)-(?P<name>[\u4e00-\u9fff·]{2,6})$", text)
        if not match:
            continue
        name = match.group("name")
        # 页面标题采用“职务-姓名”的展示顺序；姓名已由同一标题的完整匹配
        # 单独提取，依据说明只保留可验证的职务标题，避免展示用连字符和姓名混入证据。
        duty = match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        link = title_node.find_next("a", href=True)
        href = str(link.get("href") or "") if link else ""
        detail_url = urljoin(base_url, href) if href and not href.startswith(("#", "javascript:")) else ""
        source_url = str(page_rule.get("url") or "")
        if detail_url.rstrip("/") == source_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "S_CAE_CN_LEADER_TITLE_V1",
                "selector_summary": ".right_md_yld .yld_bluetop",
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
