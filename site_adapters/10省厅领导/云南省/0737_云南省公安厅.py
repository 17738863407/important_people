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
    """去除姓名中的装饰性空白和尾部标点。"""
    return clean_text(value).replace(" ", "").strip("，,。；;：:")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析云南省公安厅领导信息正文段落。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for paragraph in soup.select(".content.clearfix .readnr p"):
        name_node = paragraph.select_one("strong")
        if not name_node:
            continue
        raw_name = clean_text(name_node.get_text(" ", strip=True))
        name = normalize_name(raw_name)
        full_text = clean_text(paragraph.get_text(" ", strip=True))
        if not name or len(name) < 2 or not full_text:
            continue
        duty = full_text.replace(raw_name, "", 1).strip(" ，,。；;：:")
        if not duty and "，" in full_text:
            duty = full_text.split("，", 1)[1].strip(" ，,。；;：:")
        if not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_yunnan_police_readnr_strong_v1",
            }
        )
    return rows


PAGE_RULE = {'rule_id': '0737',
 'domain': 'gonganting.yn.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_yunnan_police_readnr_strong_v1',
 'leader_region_selector': '.content.clearfix .readnr p',
 'name_selector': '.content.clearfix .readnr p strong',
 'duty_selector': '.content.clearfix .readnr p',
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
 'locator': {'css': {'leader_region_selector': '.content.clearfix .readnr p',
                     'name_selector': '.content.clearfix .readnr p strong',
                     'duty_selector': '.content.clearfix .readnr p',
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
