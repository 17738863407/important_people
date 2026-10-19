from __future__ import annotations

import sys
from pathlib import Path
def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")



def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析江西省财政厅领导分工表格，避免把“个人简历”误识别为姓名。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    zoom = soup.select_one("#zoom") or soup
    outer_table = zoom.find("table")
    if outer_table is None:
        return []

    tbody = outer_table.find("tbody") or outer_table
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=#zoom > table person rows；"
        "name=person row first a；duty=个人简历中的现任句；detail=none；api_enabled=False"
    )

    for tr in tbody.find_all("tr", recursive=False):
        row_text = re.sub(r"\s+", " ", tr.get_text(" ", strip=True)).strip()
        if "工作分工" not in row_text or "个人简历" not in row_text:
            continue

        name_node = tr.find("a")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if name in seen_names:
            continue

        resume_match = re.search(r"个人简历[：:](?P<resume>.*?)(?=$|工作分工[：:])", row_text)
        resume_text = resume_match.group("resume").strip() if resume_match else row_text
        duty_match = re.search(r"现任(?P<duty>[^。；;]+)", resume_text)
        duty = duty_match.group("duty").strip(" ，,。；;") if duty_match else ""
        if not duty:
            continue

        work_match = re.search(r"工作分工[：:](?P<work>.*?)(?=个人简历[：:]|$)", row_text)
        work_text = work_match.group("work").strip() if work_match else ""
        evidence = duty

        seen_names.add(name)
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high",
                "parser": "page_inline_jxf_jiangxi_leader_table_v1",
                "selector_summary": selector_summary,
            }
        )

    return rows


PAGE_RULE = {'rule_id': '1279',
 'domain': 'jxf.jiangxi.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_jxf_jiangxi_leader_table_v1',
 'leader_region_selector': '#zoom > table',
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
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '表格中含工作分工长文，旧配置仍使用 online/browser_dom 并保留详情链额度，容易增加无效消耗；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '#zoom > table',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面包含领导分工表格，直接解析实时 HTML'},
             'migration': {'source': 'legacy_page_rule',
                           'verified_status': 'verified_online',
                           'behavior_changed': False}}}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    current_file = Path(__file__).resolve()
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
