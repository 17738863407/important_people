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
    """压缩 HTML 文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析北京市政协领导分区。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    source_url = final_url or str(page_rule.get("url", ""))
    section = soup.select_one("#sld_point_04 + .ld_list")
    if section is None:
        return rows

    for card in section.select("a"):
        title_node = card.select_one("p.title1")
        if title_node is None:
            continue

        name_node = title_node.select_one("i")
        duty_node = title_node.select_one("b")
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "") if name_node is not None else ""
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node is not None else ""

        if not duty:
            text = clean_text(title_node.get_text(" ", strip=True))
            match = re.fullmatch(r"([^：:]{1,12})[：:](.+)", text)
            if match is not None:
                duty = clean_text(match.group(1))
                name = clean_text(match.group(2)).replace(" ", "")

        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        href = str(card.get("href") or "")
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": urljoin(source_url, href) if href else source_url,
                "name": name,
                "duty": duty,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_beijing_cppcc_section_v1",
            }
        )
    return rows


PAGE_RULE = {'rule_id': '0116',
 'domain': 'www.beijing.gov.cn',
 'page_type': '职务分组名单页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_inline_beijing_cppcc_section_v1',
 'leader_region_selector': '#sld_point_04 + .ld_list',
 'name_selector': 'p.title1 i',
 'duty_selector': 'p.title1 b',
 'detail_link_selector': '#sld_point_04 + .ld_list a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
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
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '#sld_point_04 + .ld_list',
                     'name_selector': 'p.title1 i',
                     'duty_selector': 'p.title1 b',
                     'detail_link_selector': '#sld_point_04 + .ld_list a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '当前脚本缺少可复现 api 配置；本次迁移保留旧定位字段，后续逐页接口探测', 'probe_status': '需要逐页探测'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'pending_root', 'behavior_changed': False}}}


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
