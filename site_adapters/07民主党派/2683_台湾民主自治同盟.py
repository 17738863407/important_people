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

PAGE_RULE = {'rule_id': '2683',
 'domain': 'www.taimeng.org.cn',
 'page_type': '图片名单型',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '图片承载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'taimeng_current_leaders_group_v1',
 'leader_region_selector': '#main .tmly .right .xrld',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复；候选链接含页脚导航噪声',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div#main',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线现任领导HTML已列出姓名，职务由主席/副主席分组确定'},
             'migration': {}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析台湾民主自治同盟现任领导页分组姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#main .xrld")
    if root is None:
        return []
    organization = str(page_rule["organization"])
    page_url = str(page_rule["url"])
    parser = str(page_rule["parser"])
    rows = []
    seen: set[str] = set()
    for group in root.select("dl, ul"):
        title = group.select_one("dt, h3")
        duty = re.sub(r"\s+", "", title.get_text(" ", strip=True) if title else "")
        for item in group.select("dd, li"):
            link = item.select_one("p a[href]") or item.select_one("a[href]")
            name = re.sub(r"\s+", "", link.get_text(" ", strip=True) if link else "")
            if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen or not duty:
                continue
            seen.add(name)
            rows.append(
                {
                    "organization": organization,
                    "url": page_url,
                    "name": name,
                    "duty": duty,
                    "detail_url": urljoin(final_url, link.get("href", "")),
                    "evidence": duty,
                    "parser": parser,
                    "selector_summary": "#main .xrld dl/ul分组标题 + dd/li姓名链接",
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
