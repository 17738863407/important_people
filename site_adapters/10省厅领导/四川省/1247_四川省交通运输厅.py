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

PAGE_RULE = {'rule_id': '1247',
 'domain': 'jtt.sc.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_sichuan_transport_leader_paragraph_v1',
 'leader_region_selector': '.jgjj_content_leader > p',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '旧规则使用 detail_chain 且最多允许 50 个详情链接，实际列表页已含姓名和现任职务，继续抓详情会混入机构列表和栏目链接；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.jgjj_content_leader > p',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """姓名内部不保留排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def clean_duty(value: str) -> str:
    """清理职务文本。"""
    duty = normalize_space(value).strip(" ：:，。")
    if duty.startswith("现任"):
        duty = duty[2:]
    for prefix in ("四川省交通运输厅", "省交通运输厅"):
        if duty.startswith(prefix):
            duty = duty[len(prefix):]
    duty = re.sub(r"\s*、\s*", "、", duty)
    duty = re.sub(r"\s*，\s*", "，", duty)
    duty = duty.replace("党组成员，副厅长", "党组成员、副厅长")
    return duty.strip(" ，。")


def clean_evidence(value: str) -> str:
    """按当前页面职务节点规则清理依据说明。"""
    evidence = normalize_space(value)
    evidence = re.sub(r"^现任\s*", "", evidence)
    evidence = re.sub(r"[（(]\s*兼\s*[）)]", "", evidence)
    return evidence.strip(" 。")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析四川省交通运输厅领导简介段落。"""
    soup = BeautifulSoup(html, "html.parser")
    page_url = final_url
    parser = str(page_rule.get("parser", ""))
    selector_summary = "strategy=custom_parse_page；selector=.jgjj_content_leader > p；field=首个链接姓名+span 现任职务"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(".jgjj_content_leader > p"):
        links = item.select("a[href]")
        if not links:
            continue
        name = clean_name(links[0].get_text(" ", strip=True))
        duty_node = item.select_one("span a[href]") or (links[1] if len(links) > 1 else None)
        duty_text = duty_node.get_text(" ", strip=True) if duty_node else ""
        duty = clean_duty(duty_text)
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "order": len(rows) + 1,
                "detail_url": urljoin(page_url, links[0].get("href", "")),
                "evidence": clean_evidence(duty_text),
                "parser": parser,
                "selector_summary": selector_summary,
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
