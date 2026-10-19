from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0417',
 'domain': 'district.ce.cn',
 'page_type': '人物表格页',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'S013_ce_district_leader_list_v1',
 'source_parser': 'paragraph_profile_parser_v1',
 'leader_region_selector': '.main .ren2, .main .TRS_Editor, .content .TRS_Editor, .trs_editor_view',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': [],
                   'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'person_name_link',
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '是',
 'profile_judgement': '网页画像通过_可用于该网页后续更新',
 'filter_policy': 'strong_no_wordlist'}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅解析中国经济网页“任免动态”之前的现任政协领导链接。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".content .TRS_Editor") or soup.select_one(".trs_editor_view")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for paragraph in region.select("p"):
        if "任免动态" in paragraph.get_text(" ", strip=True):
            break
        for link in paragraph.select("a[href]"):
            text = "".join(link.get_text(" ", strip=True).split())
            match = re.fullmatch(r"(主席|副主席|秘书长)([\u4e00-\u9fff·]{2,8}?)(?:简历)?", text)
            if match is None:
                continue
            duty, name = match.groups()
            key = (name, duty)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(final_url or str(page_rule.get("url", "")), str(link.get("href", ""))),
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
