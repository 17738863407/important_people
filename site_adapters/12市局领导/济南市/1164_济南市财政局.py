from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1164',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_jinan_finance_label_table_v2',
 'leader_region_selector': 'div#zoom > div > table',
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
                     'max_detail_links': 0},
 'risk_flag': '领导信息为单表重复姓名、职务、领导简历、工作分工字段；只取姓名与职务标签之间的值，排除简历和分工',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div#zoom > div > table',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'pending_root', 'behavior_changed': False}}}


def clean_text(value: str) -> str:
    """压缩排版空白，并消除中文字符之间的异常字距。"""
    text = re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return re.sub(r"\s*([、，,；;：:])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按姓名、职务和领导简历标签边界提取领导信息。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("div#zoom table")
    if table is None:
        raise RuntimeError("领导信息页缺少 div#zoom table")
    text = clean_text(table.get_text(" ", strip=True))
    matches = list(
        re.finditer(
            r"姓名\s*[:：]\s*(?P<name>[\u4e00-\u9fff·\s]{2,12}?)\s*"
            r"职务\s*[:：]\s*(?P<duty>.+?)\s*领导简历\s*[:：]",
            text,
        )
    )
    if not matches:
        raise RuntimeError("领导信息表未找到姓名—职务—领导简历字段组")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for match in matches:
        name = re.sub(r"\s+", "", match.group("name"))
        duty = clean_text(match.group("duty")).strip("。")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            raise RuntimeError(f"领导姓名格式异常：{name or '<空>'}")
        if not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "page_inline_jinan_finance_label_table_v2",
                "selector_summary": "div#zoom table；姓名—职务—领导简历标签边界",
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
