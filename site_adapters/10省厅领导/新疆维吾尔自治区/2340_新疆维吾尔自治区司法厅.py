from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2340',
 'domain': 'sft.xinjiang.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_xinjiang_justice_name_duty_paragraphs_v1',
 'leader_region_selector': '.page.scroll-box',
 'name_selector': '',
 'duty_selector': '',
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
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.page.scroll-box',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'verified_online', 'behavior_changed': True}}}


def _clean_text(value: str) -> str:
    value = value.replace("\u3000", " ").replace("\xa0", " ")
    return " ".join(value.split()).strip()


def _clean_duty(value: str) -> str:
    return _clean_text(value).replace(" ", "")


def _strip_label(value: str, label: str) -> str:
    text = _clean_text(value)
    for prefix in (f"{label}：", f"{label}:"):
        if text.startswith(prefix):
            return _clean_text(text[len(prefix):])
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析新疆维吾尔自治区司法厅党委班子成员正文中的姓名/职务段落。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".page.scroll-box")
    if not scope:
        return []
    lines = [_clean_text(node.get_text(" ", strip=True)) for node in scope.select("p")]
    lines = [line for line in lines if line]
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    current_name = ""
    for line in lines:
        name = _strip_label(line, "姓名")
        if name:
            current_name = name.replace(" ", "")
            continue
        duty_text = _strip_label(line, "职务")
        if duty_text and current_name:
            duty = _clean_duty(duty_text)
            key = (current_name, duty)
            if key not in seen:
                seen.add(key)
                records.append(
                    {
                        "name": current_name,
                        "duty": duty,
                        "detail_url": "",
                        "evidence": duty,
                    }
                )
            current_name = ""
    return records


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
