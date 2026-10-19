from __future__ import annotations

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

PAGE_RULE = {'rule_id': '0622',
 'domain': 'www.gansu.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'chrome_cdp',
 'parser': 'page_inline_gansu_gov_leader_window_v1',
 'leader_region_selector': '.ldzc_right',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
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
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.ldzc_right',
                     'name_selector': '.leaderright span, h2.compt',
                     'duty_selector': '.ldzc_title, .leaderright p',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False,
                     'reason': '页面对普通 HTTP/Playwright 请求返回 412 校验页，使用本机 Chrome CDP 获取在线渲染 DOM',
                     'probe_status': 'chrome_cdp_verified'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'verified_online', 'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def normalize_name(value: str) -> str:
    """清理姓名中的排版空格。"""
    return clean_text(value).replace(" ", "")


def append_row(
    rows: list[dict[str, str]],
    seen: set[str],
    page_rule: dict[str, object],
    source_url: str,
    name: str,
    duty: str,
    href: str,
    selector_summary: str,
) -> None:
    """按统一字段追加一条领导记录。"""
    if not name or not duty or name in seen:
        return
    seen.add(name)
    detail_url = urljoin(source_url, href) if href and not href.startswith(("#", "javascript:")) else ""
    if detail_url.rstrip("/") == source_url.rstrip("/"):
        detail_url = ""
    rows.append(
        {
            "name": name,
            "duty": duty,
            "detail_url": detail_url,
            "evidence": duty,
            "confidence": "high",
            "parser": "page_inline_gansu_gov_leader_window_v1",
            "selector_summary": selector_summary,
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析甘肃省人民政府领导之窗右侧“省政府领导”区域。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".ldzc_right")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    source_url = final_url or str(page_rule.get("url", ""))

    leader_link = region.select_one(".leader a[href]")
    if leader_link is not None:
        name = normalize_name((leader_link.select_one(".leaderright span") or leader_link).get_text(" ", strip=True))
        duty = clean_text((leader_link.select_one(".leaderright p") or leader_link).get_text(" ", strip=True))
        append_row(
            rows,
            seen,
            page_rule,
            source_url,
            name,
            duty,
            leader_link.get("href", ""),
            "省政府领导主卡片",
        )

    for block in region.select("div"):
        title_node = block.select_one("h2.ldzc_title")
        if title_node is None or block.select_one(".leaderimg") is not None:
            continue
        duty = clean_text(title_node.get_text(" ", strip=True))
        for link in block.select("ul.ldzclist a[href]"):
            name_node = link.select_one("h2.compt")
            name = normalize_name(name_node.get_text(" ", strip=True) if name_node else link.get_text(" ", strip=True))
            append_row(
                rows,
                seen,
                page_rule,
                source_url,
                name,
                duty,
                link.get("href", ""),
                f"{duty}列表",
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
