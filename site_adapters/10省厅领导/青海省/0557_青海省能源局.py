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
    """压缩 HTML 文本中的全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def clean_chinese_space(value: str) -> str:
    """去掉中文字符之间的异常空格，保留正常标点。"""
    import re

    text = clean_text(value)
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口页面顺序提取全部领导卡片及其完整原始职务。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    source_url = str(page_rule.get("url") or final_url)
    for card in soup.select("a[href]"):
        name_node = card.select_one("p.nm")
        duty_node = card.select_one("p.js")
        if name_node is None or duty_node is None:
            continue
        name = clean_chinese_space(name_node.get_text(" ", strip=True)).replace(" ", "")
        duty = clean_chinese_space(duty_node.get_text(" ", strip=True)).strip("。")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            raise RuntimeError(f"领导卡片姓名格式异常：{name or '<空>'}")
        if not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", source_url)),
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url or source_url, str(card.get("href") or "")),
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_qinghai_energy_parent_leader_cards_v3",
            }
        )
    if not rows:
        raise RuntimeError("当前入口未解析出有效领导卡片")
    return rows


PAGE_RULE = {'rule_id': '0557',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_qinghai_energy_parent_leader_cards_v3',
 'leader_region_selector': 'a[href]中同时含p.nm和p.js的领导卡片',
 'name_selector': 'p.nm',
 'duty_selector': 'p.js完整原始职务',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '领导之窗', 'end_anchor': '', 'include_selectors': ['p.nm', 'p.js'], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0},
 'risk_flag': '按当前用户验收口径采集规则入口全部领导卡片；保持页面原序和完整原始职务，不按职务关键词筛除人物',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.sidebar .info-list > p',
                     'name_selector': '职务冒号后姓名',
                     'duty_selector': '职务冒号前文本',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '党组书记，局长',
                                       'end_anchor': '联系电话',
                                       'include_selectors': ['.sidebar .info-list > p'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'sequential_static_html_builder',
                           'verified_status': 'verified_snapshot',
                           'behavior_changed': True}}}


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
