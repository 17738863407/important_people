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

PAGE_RULE = {'rule_id': '2291',
 'domain': 'www.sdzx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_shandong_cppcc_grouped_roles_v1',
 'leader_region_selector': '.szyw_right .zxnr.pt25',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '.szyw_right .zxnr.pt25 ul.leftNUl a[href], .szyw_right .zxnr.pt25 ul.rightNUl a[href]',
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
 'locator': {'css': {'leader_region_selector': '.szyw_right .zxnr.pt25',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '.szyw_right .zxnr.pt25 ul.leftNUl a[href], .szyw_right .zxnr.pt25 ul.rightNUl a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {}}}


def _clean_text(value: str) -> str:
    value = value.replace("\u3000", " ").replace("\xa0", " ")
    return " ".join(value.split()).strip()


def _clean_name(value: str) -> str:
    return _clean_text(value).replace(" ", "")


def _append_role(
    records_by_name: dict[str, dict[str, str]],
    order: list[str],
    name: str,
    duty: str,
    detail_url: str,
    organization: str,
    final_url: str,
) -> None:
    if name not in records_by_name:
        order.append(name)
        records_by_name[name] = {
            "organization": organization,
            "url": final_url,
            "name": name,
            "duty": duty,
            "detail_url": detail_url,
            "evidence": duty,
        }
        return
    existing = records_by_name[name]
    duties = [part.strip() for part in existing["duty"].split("；") if part.strip()]
    if duty not in duties:
        duties.append(duty)
        existing["duty"] = "；".join(duties)
        existing["evidence"] = existing["duty"]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析山东省政协领导班子成员，并按姓名聚合政协职务和党组职务。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".szyw_right .zxnr.pt25")
    if not scope:
        return []
    records_by_name: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for role_node in scope.select("ul.leftPUl, ul.rightPUl"):
        duty = _clean_text(role_node.get_text(" ", strip=True)).replace(" ", "")
        if not duty:
            continue
        name_node = role_node.find_next_sibling("ul")
        if not name_node:
            continue
        classes = set(name_node.get("class") or [])
        if not ({"leftNUl", "rightNUl"} & classes):
            continue
        for link in name_node.select("a[href]"):
            name = _clean_name(link.get_text(" ", strip=True))
            href = link.get("href", "")
            if not name or not href:
                continue
            _append_role(
                records_by_name,
                order,
                name,
                duty,
                urljoin(final_url, href),
                str(page_rule.get("organization", "")),
                final_url,
            )
    return [records_by_name[name] for name in order]


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
