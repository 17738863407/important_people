from __future__ import annotations

import sys
from pathlib import Path


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
    """页面姓名中含排版空格，抽取时去除。"""
    return clean_text(value).replace(" ", "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析共青团中央书记处同志卡片。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    source_url = final_url or str(page_rule.get("url", ""))
    seen: set[str] = set()

    for item in soup.select(".tuan_box_jigouyou.show .tuan_jigou_men_copy"):
        name_node = item.select_one(".tuan_jigou_men_word h2")
        duty_node = item.select_one(".tuan_jigou_men_word p")
        name = normalize_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty_parts = [clean_text(part) for part in duty_node.stripped_strings] if duty_node else []
        duty = "；".join(part for part in duty_parts if part)
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_cyol_secretariat_member_cards_v1",
            }
        )
    return rows


PAGE_RULE = {'rule_id': '0742',
 'domain': 'www.gqt.org.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_cyol_secretariat_member_cards_v1',
 'leader_region_selector': '.tuan_box_jigouyou.show .tuan_jigou_men_copy',
 'name_selector': '.tuan_box_jigouyou.show .tuan_jigou_men_word h2',
 'duty_selector': '.tuan_box_jigouyou.show .tuan_jigou_men_word p',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
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
 'locator': {'css': {'leader_region_selector': '.tuan_box_jigouyou.show .tuan_jigou_men_copy',
                     'name_selector': '.tuan_box_jigouyou.show .tuan_jigou_men_word h2',
                     'duty_selector': '.tuan_box_jigouyou.show .tuan_jigou_men_word p',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule',
                           'verified_status': 'verified_online',
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
