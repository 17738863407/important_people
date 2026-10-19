from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3396',
 'domain': 'zrzy.gansu.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'gansu_natural_resources_leader_window_v1',
 'leader_region_selector': 'html > body > div.xinxigongkai_box:nth-of-type(3)',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'max_detail_links': 50},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'html > body > div.xinxigongkai_box:nth-of-type(3)',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线浏览器 DOM 列出领导之窗姓名和人物链接'}}}


def clean_name(value: str) -> str:
    """清理姓名中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "")


def clean_text(value: str) -> str:
    """压缩详情简介中的排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导之窗顺序读取姓名，并从对应详情简介提取完整现任句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select("div.xinxigongkai_box")
    region = next(
        (node for node in regions if node.select('a[href*="ldzc.shtml"]')),
        soup,
    )
    parser = str(page_rule["parser"])
    selector_summary = "领导之窗区域a[href*=ldzc.shtml]实时姓名卡片"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in region.select('a[href*="ldzc.shtml"]'):
        name = clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, link.get("href") or "")
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            raise RuntimeError(f"{name}的详情链接等于机构入口页")
        detail_result = fetch_html_with_strategy(detail_url, strategy="online", timeout=30)
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        intro = detail_soup.select_one(".gzfg1")
        intro_text = clean_text(intro.get_text(" ", strip=True) if intro else "")
        evidence_match = re.search(r"现任[^。]*。", intro_text)
        if name not in intro_text or evidence_match is None:
            raise RuntimeError(f"{name}详情简介未找到可回指的完整现任句")
        evidence = re.sub(
            r"^现任(?:职务)?\s*[：:]?\s*",
            "",
            evidence_match.group(0),
        )
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_result.final_url,
                "evidence": evidence,
                "parser": parser,
                "selector_summary": f"{selector_summary}；详情=.gzfg1内完整现任句",
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
