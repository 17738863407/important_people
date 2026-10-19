from __future__ import annotations

import sys
from pathlib import Path
def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")



PAGE_RULE = {'rule_id': '1556',
 'domain': 'www.mfa.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': 'mfa_leader_info_clearfix',
 'reuse_scope': 'page_structure',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'S004_mfa_main_leader_info_v1',
 'leader_region_selector': '.main .clearfix',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': 'li a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'list_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '.main .clearfix li a[href]',
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.main .clearfix',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': 'li a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'success_dir', 'behavior_changed': False}}}


def clean_text(value: str) -> str:
    """压缩详情页文本空白。"""
    import re

    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从主要官员列表动态发现详情页，并在线提取职务节点。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".main .clearfix li a[href]"):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, link.get("href") or "") if final_url else ""
        if not detail_url:
            continue
        detail_result = fetch_by_raw_requests(detail_url)
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        duty_parts: list[str] = []
        for node in detail_soup.select("p[style*='text-align'] strong"):
            text = clean_text(node.get_text(" ", strip=True))
            if re.search(r"书记|部长|组长|主任|委员", text) or (duty_parts and text.startswith("（")):
                duty_parts.append(text)
            elif duty_parts:
                break
        duty = " ".join(duty_parts)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "list=.main .clearfix li a[href]；detail=p[style*=text-align] strong",
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


