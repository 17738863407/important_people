from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3080',
 'domain': 'www.xizangzx.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'raw_http',
 'parser': 'xizang_cppcc_api_current_duty_v1',
 'leader_region_selector': 'cms article API artCategoryId=2498，排除新闻稿噪声',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '接口返回含新闻稿噪声；第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': 'div#app',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': True, 'reason': '接口返回政协领导姓名、分类和artContent现任职务句'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'fixed_verified',
                           'behavior_changed': True}}}


def clean_evidence(value: str) -> str:
    """清理接口现任句的固定标签、句末标点及职责分句。"""
    text = re.sub(r"^(?:现任|职务|现任职务)[：:]?", "", re.sub(r"\s+", " ", value or "").strip()).rstrip("。")
    return re.sub(r"，(?:分管|主持|负责|协管).*$", "", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析西藏自治区政协接口数据中可见政协领导的现任职务。"""
    api_url = "https://cms.xizangzx.gov.cn:8082/api/cms/article/getListDataPage"
    response = requests.post(
        api_url,
        json={"artCategoryId": 2498, "pageNum": 1, "pageSize": 1000},
        timeout=60,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    articles = response.json().get("data", [])
    ordered_articles = []
    for category_id in ("2551", "2554", "2555", "2552", "2553"):
        ordered_articles.extend(
            article for article in articles
            if category_id in str(article.get("artCategoryId", "")).split(",")
        )
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for article in ordered_articles:
        name = re.sub(r"\s+", "", str(article.get("artTitle", "")))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen_names:
            continue
        content = BeautifulSoup(str(article.get("artContent", "")), "html.parser").get_text(" ", strip=True)
        match = re.search(r"现任[^。]*。", re.sub(r"\s+", " ", content))
        if not match or "政协" not in match.group(0):
            continue
        sentence = clean_evidence(match.group(0))
        seen_names.add(name)
        rows.append(
            {
                "organization": str(page_rule["organization"]),
                "url": str(page_rule["url"]),
                "name": name,
                "duty": sentence,
                "detail_url": "",
                "evidence": sentence,
                "parser": str(page_rule["parser"]),
                "selector_summary": "POST /api/cms/article/getListDataPage；artCategoryId=2498；子分类2551/2554/2555/2552/2553；artTitle+artContent现任句",
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
