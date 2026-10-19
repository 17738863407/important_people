from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2650',
 'domain': 'www.sxrd.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'inline_parser_handles_fetch': True,
 'inline_fetch_collector': 'requests',
 'parser': 'shaanxi_people_congress_leader_window_v1',
 'leader_region_selector': '首页领导之窗',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"browser_dom","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '新闻人物或正文干扰',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div#app',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线渲染的首页领导之窗直接列出常委会领导'}}}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def _extract_name(link: Tag) -> str:
    text = _clean_text(link.get_text(" ", strip=True))
    if not text:
        image = link.select_one("img[alt], img[title]")
        if image:
            text = _clean_text(image.get("alt") or image.get("title") or "")
    text = re.sub(r"^(?:主任|副主任|秘书长)\s*[：:]?\s*", "", text)
    return text.replace(" ", "") if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", text.replace(" ", "")) else ""


def _nearest_group_duty(link: Tag) -> str:
    for node in [link, *list(link.parents)[:4]]:
        if not isinstance(node, Tag):
            continue
        text = _clean_text(node.get_text(" ", strip=True))
        if len(text) <= 30:
            for duty in ("秘书长", "副主任", "主任"):
                if duty in text:
                    return duty
    for node in link.find_all_previous(limit=80):
        text = _clean_text(node.get_text(" ", strip=True))
        if text in {"主任", "副主任", "秘书长"}:
            return text
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """调用首页领导之窗同源公开接口，按主任、副主任、秘书长分组抽取。"""
    page_url = str(page_rule["url"])
    parsed_page = urlparse(page_url)
    api_url = (
        f"{parsed_page.scheme}://{parsed_page.netloc}/sxrdcms/"
        "cmsview.action?method=getCmsColumnInfo"
    )
    response = requests.post(
        api_url,
        data={"columnunid": "J1622a94674e47c3921d99f50babb249"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise RuntimeError("常委会组成人员接口返回结构异常")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in payload[0].get("children") or []:
        if not isinstance(group, dict):
            continue
        duty = _clean_text(str(group.get("columnname") or ""))
        if duty not in {"主任", "副主任", "秘书长"}:
            continue
        for person in group.get("infochildren") or []:
            if not isinstance(person, dict):
                continue
            name = _clean_text(str(person.get("title") or "")).replace(" ", "")
            unid = _clean_text(str(person.get("unid") or ""))
            if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not unid or name in seen:
                continue
            seen.add(name)
            query = urlencode({"unid": unid, "columnname": "常委会组成人员"})
            rows.append(
                {
                    "url": page_url,
                    "name": name,
                    "duty": duty,
                    "detail_url": urljoin(page_url, f"#/details?{query}"),
                    "evidence": duty,
                    "parser": str(page_rule["parser"]),
                    "selector_summary": "领导之窗同源接口分组：主任/副主任/秘书长",
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
