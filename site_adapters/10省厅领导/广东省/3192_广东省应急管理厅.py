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

PAGE_RULE = {'rule_id': '3192',
 'domain': 'yjgl.gd.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '官方栏目JSON接口',
 'fetch_mode': 'online',
 'inline_parser_handles_fetch': True,
 'inline_fetch_collector': 'requests',
 'extract_mode': 'api_to_detail',
 'collector': 'custom_api_http',
 'parser': 'guangdong_emergency_management_leader_api_v2',
 'leader_region_selector': 'api:/gkmlpt/api/all/{栏目编号}',
 'name_selector': 'articles[].title',
 'duty_selector': 'articles[].abstract或对应详情页现任句',
 'detail_link_selector': 'articles[].post_url',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '详情页含历史括号摘要，需以正文现任职务句为准',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_api',
 'locator': {'api': {'enabled': True,
                     'method': 'GET',
                     'endpoint': '/gkmlpt/api/all/{栏目编号}?page=1&sid=122',
                     'data_path': 'articles',
                     'name_field': 'title',
                     'detail_field': 'post_url',
                     'evidence_field': 'abstract'}}}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def fetch_current_position(session: requests.Session, detail_url: str) -> str:
    try:
        response = session.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        response.raise_for_status()
    except requests.RequestException:
        return ""
    response.encoding = response.apparent_encoding or response.encoding
    text = clean_text(BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True))
    match = re.search(r"(现任[^。]*。)", text)
    return clean_text(match.group(1)).removeprefix("现任").removesuffix("。") if match else ""


def extract_current_position(text: str) -> str:
    """从官网摘要或详情正文中提取完整现任句。"""
    match = re.search(r"现任[^。]*。", clean_text(text))
    if match is None:
        return ""
    return clean_text(match.group(0)).removeprefix("现任").removesuffix("。")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按官方领导信息栏目接口顺序解析姓名、现任职务与详情页。"""
    del html, final_url
    entry_url = str(page_rule.get("url", ""))
    category_match = re.search(r"#(?P<category>\d+)$", entry_url)
    if category_match is None:
        raise RuntimeError("领导信息入口缺少栏目编号")
    category_id = category_match.group("category")
    api_url = f"https://yjgl.gd.gov.cn/gkmlpt/api/all/{category_id}?page=1&sid=122"
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        api_url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": entry_url},
        timeout=25,
    )
    response.raise_for_status()
    articles = response.json().get("articles", [])
    if not isinstance(articles, list):
        raise RuntimeError("领导信息接口 articles 字段类型异常")
    parser = str(page_rule["parser"])
    selector = "api:articles[].title/abstract/post_url"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for article in articles:
        if not isinstance(article, dict):
            continue
        name = re.sub(r"\s+", "", clean_text(str(article.get("title", ""))))
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or name in seen:
            continue
        detail_url = str(article.get("post_url") or article.get("url") or "").strip()
        evidence = extract_current_position(str(article.get("abstract", "")))
        if not evidence and detail_url:
            evidence = fetch_current_position(session, detail_url)
        if not evidence:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": parser,
                "selector_summary": selector,
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
