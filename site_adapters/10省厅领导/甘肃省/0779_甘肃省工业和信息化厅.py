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
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def normalize_name(value: str) -> str:
    """姓名中可能有排版空格或窄空格。"""
    return clean_text(value).replace(" ", "")


def split_name_duty(text: str) -> tuple[str, str]:
    """从领导链接文本中拆分姓名和职务。"""
    import re

    value = clean_text(text)
    if "：" in value or ":" in value:
        duty, name = value.replace(":", "：", 1).split("：", 1)
        return normalize_name(name), clean_text(duty)
    match = re.match(r"^([\u4e00-\u9fff]\s*[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff])?)(?=\s*(?:党组|副厅长|驻厅|一级|二级))(.+)$", value)
    if not match:
        return "", ""
    return normalize_name(match.group(1)), clean_text(match.group(2))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析甘肃省工业和信息化厅领导之窗链接列表。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    source_url = final_url or str(page_rule.get("url", ""))
    seen: set[str] = set()

    for link in soup.select("a[href*='/gxt/c119'][href*='2025xxgk_ldxq_dy.shtml']"):
        name, duty = split_name_duty(link.get_text(" ", strip=True))
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(source_url, str(link.get("href") or ""))
        if detail_url.rstrip("/") == source_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_gansu_industry_leader_links_v1",
            }
        )
    return rows


PAGE_RULE = {'rule_id': '0779',
 'domain': 'gxt.gansu.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_inline_gansu_industry_leader_links_v1',
 'leader_region_selector': "a[href*='/gxt/c119'][href*='2025xxgk_ldxq_dy.shtml']",
 'name_selector': "a[href*='/gxt/c119'][href*='2025xxgk_ldxq_dy.shtml']",
 'duty_selector': "a[href*='/gxt/c119'][href*='2025xxgk_ldxq_dy.shtml']",
 'detail_link_selector': "a[href*='/gxt/c119'][href*='2025xxgk_ldxq_dy.shtml']",
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'browser_dom',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': "a[href*='/gxt/c119'][href*='2025xxgk_ldxq_dy.shtml']",
                     'name_selector': "a[href*='/gxt/c119'][href*='2025xxgk_ldxq_dy.shtml']",
                     'duty_selector': "a[href*='/gxt/c119'][href*='2025xxgk_ldxq_dy.shtml']",
                     'detail_link_selector': "a[href*='/gxt/c119'][href*='2025xxgk_ldxq_dy.shtml']",
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '动态 DOM 页面沿用 CSS/HTML 定位'}}}


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
