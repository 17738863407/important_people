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
    return " ".join(str(value or "").replace("\u3000", " ").split())


def normalize_name(value: str) -> str:
    """清理姓名内部用于排版的空格。"""
    return clean_text(value).replace(" ", "").replace("\u2002", "").replace("\u2003", "")


def extract_current_duty(text: str) -> tuple[str, str]:
    """从“现任……”简介句中提取当前职务。"""
    import re

    cleaned = clean_text(text)
    match = re.search(r"现任[^。]*。?", cleaned)
    if not match:
        return "", ""
    duty = match.group(0).removeprefix("现任")
    duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty).rstrip("。；; ")
    return duty, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析甘肃省公安厅响应式表格领导块。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    _ = final_url, page_rule
    seen: set[str] = set()

    for block in soup.select(".responsive-table table"):
        cells = block.select("tr > td")
        if len(cells) < 2:
            continue

        bio = clean_text(cells[1].get_text(" ", strip=True))
        match = re.match(r"^\s*([\u4e00-\u9fff·\s\u2002\u2003]{2,10})[，,]", bio)
        name = normalize_name(match.group(1)) if match else ""
        if not name:
            name_candidates = [
                normalize_name(node.get_text(" ", strip=True))
                for node in cells[0].select("p, span")
                if normalize_name(node.get_text(" ", strip=True))
            ]
            name = name_candidates[-1] if name_candidates else ""

        duty, evidence = extract_current_duty(bio)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high",
                "parser": "page_inline_gansu_police_responsive_tables_v1",
            }
        )
    return rows


PAGE_RULE = {'rule_id': '0625',
 'domain': 'gat.gansu.gov.cn',
 'page_type': '人物表格页',
 'structure_group': 'gansu_police_responsive_leader_tables',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'chrome',
 'extract_mode': 'list_direct',
 'collector': 'chrome_cdp',
 'parser': 'page_inline_gansu_police_responsive_tables_v1',
 'leader_region_selector': '.responsive-table table',
 'name_selector': '.responsive-table table tr > td:nth-child(1) p:last-child',
 'duty_selector': '.responsive-table table tr > td:nth-child(2) p',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '甘肃省公安厅领导',
                   'end_anchor': '关闭窗口',
                   'include_selectors': ['.responsive-table table'],
                   'exclude_selectors': ['网站导航', '无障碍工具']},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'chrome_cdp',
                     'detail_link_selector': None,
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '普通HTTP返回412，无头Playwright返回极短空页；当前必须使用项目独立Chrome CDP取得响应式领导表格',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.responsive-table table',
                     'name_selector': '.responsive-table table tr > td:nth-child(1) p:last-child',
                     'duty_selector': '.responsive-table table tr > td:nth-child(2) p',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '甘肃省公安厅领导',
                                       'end_anchor': '关闭窗口',
                                       'include_selectors': ['.responsive-table table'],
                                       'exclude_selectors': ['网站导航', '无障碍工具']}},
             'api': {'enabled': False, 'reason': '普通HTTP受412防护，未发现可复现人物接口，使用Chrome CDP渲染DOM'}}}


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
