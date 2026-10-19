from __future__ import annotations

import re
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

PAGE_RULE = {'rule_id': '0985',
 'domain': 'www.hmo.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_hmo_leader_script_cards_v1',
 'leader_region_selector': '#mbLeader',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '#mbLeader a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '领导卡片由首条 DOM 与脚本字符串共同渲染；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '#mbLeader',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '#mbLeader a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '静态 HTML 直出页面使用 CSS/HTML 定位解析'},
             'migration': {}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def parse_card_html(fragment: str, base_url: str, rule: dict) -> dict[str, str] | None:
    soup = BeautifulSoup(fragment, "html.parser")
    name_node = soup.select_one("h2")
    duty_node = soup.select_one("p span")
    link_node = soup.select_one("a[href]")
    name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
    duty = clean_text(duty_node.get_text("", strip=True) if duty_node else "")
    duty = re.sub(r"var bt=.*?document\.write\(btr\);", "", duty).strip()
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
        return None
    detail_url = urljoin(base_url, link_node.get("href", "")) if link_node else ""
    return {
        "organization": str(rule.get("organization", "")),
        "url": base_url,
        "name": name,
        "duty": duty,
        "detail_url": detail_url,
        "evidence": duty,
        "confidence": "high",
        "parser": str(rule.get("parser", "")),
    }


def parse_page(html: str, final_url: str, rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(rule.get("url", ""))
    rows = []
    seen = set()

    for card in soup.select(".branchList .sinBox"):
        name_node = card.select_one(".name")
        duty_node = card.select_one(".desc")
        link_node = card.select_one(".name a[href], .imgBox a[href]")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue
        row = {
            "organization": str(rule.get("organization", "")),
            "url": base_url,
            "name": name,
            "duty": duty,
            "detail_url": urljoin(base_url, link_node.get("href", "")) if link_node else "",
            "evidence": duty,
            "confidence": "high",
            "parser": str(rule.get("parser", "")),
        }
        seen.add((name, duty))
        rows.append(row)

    leader = soup.select_one("#mbLeader") or soup
    for li in leader.select("li"):
        row = parse_card_html(str(li), base_url, rule)
        if not row:
            continue
        key = (row["name"], row["duty"])
        if key not in seen:
            seen.add(key)
            rows.append(row)

    for script in leader.select("script"):
        match = re.search(r"var\s+str\s*=\s*'(.*?)';", script.get_text("\n", strip=False), re.S)
        if not match:
            continue
        for fragment in match.group(1).split(";"):
            row = parse_card_html(fragment, base_url, rule)
            if not row:
                continue
            key = (row["name"], row["duty"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
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
