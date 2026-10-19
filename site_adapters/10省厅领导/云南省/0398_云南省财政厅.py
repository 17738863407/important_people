from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0398',
 'domain': 'czt.yn.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_online_ynczt_list_detail_json_v1',
 'leader_region_selector': '#artList_5186002025093996363 li',
 'name_selector': '#artList_5186002025093996363 li a',
 'duty_selector': 'detail_json.result.parent.content',
 'detail_link_selector': '#artList_5186002025093996363 li a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'person_name_link',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '#artList_5186002025093996363 li a[href]',
                     'detail_content_selector': 'detail_json.result.parent.content',
                     'max_detail_links': 0,
                     'candidate_links': []},
 'risk_flag': '第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '#artList_5186002025093996363 li',
                     'name_selector': '#artList_5186002025093996363 li a',
                     'duty_selector': 'detail_json.result.parent.content',
                     'detail_link_selector': '#artList_5186002025093996363 li a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': True, 'reason': '在线详情接口 /jeecg-boot/index/tbArticle/queryById'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'fixed_verified',
                           'behavior_changed': True}}}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析云南省财政厅领导专栏列表和详情 JSON。"""
    import re
    from urllib.parse import parse_qs, urljoin, urlparse

    import requests
    from bs4 import BeautifulSoup

    def normalize_text(value: str) -> str:
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"[\s\u3000\xa0]+", " ", value).strip()
        return value

    def extract_duty(name: str, detail_text: str) -> str:
        text = normalize_text(detail_text)
        name_pattern = r"\s*".join(map(re.escape, name))
        text = re.sub(rf"^{name_pattern}\s*", "", text)
        markers = ["主持", "分管", "协管", "负责", "1 1", "MicrosoftInternetExplorer4"]
        positions = [text.find(marker) for marker in markers if text.find(marker) >= 0]
        end = min(positions) if positions else len(text)
        duty = text[:end].strip(" ，,。；;")
        duty = re.sub(r"\s*([、，,。；;（）()])\s*", r"\1", duty)
        duty = re.sub(r"\s+", "", duty)
        return duty.strip("，,。；;")

    soup = BeautifulSoup(html, "html.parser")
    page_url = final_url
    parser = str(page_rule.get("parser", ""))
    rows: list[dict[str, str]] = []
    failed_details: list[str] = []

    for link in soup.select("#artList_5186002025093996363 li a[href]"):
        name = re.sub(r"[\s\u3000\xa0]+", "", link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        detail_url = urljoin(page_url, link.get("href") or "")
        detail_id = parse_qs(urlparse(detail_url).query).get("id", [""])[0]
        try:
            response = requests.get(
                urljoin(page_url, "/jeecg-boot/index/tbArticle/queryById"),
                params={"id": detail_id},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as error:
            failed_details.append(f"{name}({detail_id})：{error}")
            continue
        parent = (data.get("result") or {}).get("parent") or {}
        detail_text = f"{parent.get('title') or ''} {parent.get('content') or ''}"
        duty = extract_duty(name, detail_text)
        if not duty or not re.search(r"党组|厅长|巡视员|纪检|总经济师", duty):
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": parser,
                "selector_summary": "领导专栏列表+详情JSON",
            }
        )

    if failed_details:
        raise RuntimeError("领导详情接口请求失败：" + "；".join(failed_details))
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
