from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1317',
 'page_type': '人物目录详情页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '浏览器渲染',
 'fetch_mode': 'online',
 'force_browser': True,
 'extract_mode': 'list_to_detail',
 'collector': 'browser_dom',
 'parser': 'qinghai_prison_online_detail_v3',
 'leader_region_selector': 'div#wrap-xxgk',
 'name_selector': 'a.tit',
 'duty_selector': '',
 'detail_link_selector': "a.tit[href*='/zrzy/content_']",
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': True,
                     'mode': 'list_to_detail',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': "a.tit[href*='/zrzy/content_']",
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '当前入口超时或显示404，严禁从站内搜索页、历史内容页或非入口页面提取人物；只有入口路径、标题和领导目录区域同时通过校验时才解析',
 'confidence': 'failed',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'div#wrap-xxgk',
                     'name_selector': 'a.tit',
                     'duty_selector': '',
                     'detail_link_selector': "a.tit[href*='/zrzy/content_']",
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '未发现或未配置可复现接口，沿用 CSS/HTML 定位'},
             'migration': {'source': 'current_online_page', 'verified_status': 'verified_online_detail', 'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """清理网页排版空白。"""
    text = re.sub(r"[\s\u3000\u00a0\u200b]+", " ", str(value or "")).strip()
    return re.sub(r"\s*([，、；：])\s*", r"\1", text)


def fetch_detail(url: str) -> tuple[str, str]:
    """使用统一原始请求器抓取可复现的人物详情页。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(url)
    return result.html, result.final_url


def extract_detail_duty(html: str) -> str:
    """从当前详情页人物正文内提取完整现任职务。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".conTxt")
    if content is None:
        return ""
    text = clean_text(content.get_text(" ", strip=True))
    match = re.search(r"现任([^。]+)", text)
    return clean_text(match.group(1)).strip("，,。 ") if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按目录顺序抓取人物详情，并提取各自现任职务。"""
    soup = BeautifulSoup(html, "html.parser")
    entry_url = str(page_rule.get("url") or "")
    entry_path = urlsplit(entry_url).path.rstrip("/")
    final_path = urlsplit(final_url).path.rstrip("/")
    title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    body_text = clean_text(soup.get_text(" ", strip=True))
    if final_path != entry_path:
        raise RuntimeError(f"入口被跳转到非目标路径：{final_path or '<空>'}")
    if not title or re.search(r"(?:404|页面不存在|找不到页面)", f"{title} {body_text[:500]}", re.I):
        raise RuntimeError("入口当前为404或无有效页面标题")
    region = soup.select_one("div#wrap-xxgk")
    if region is None:
        raise RuntimeError("入口未找到可验证的领导目录区域 div#wrap-xxgk")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in region.select("a.tit[href*='/zwgk/fdzdgknr/jgjj/zrzy/content_']"):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        detail_url = urljoin(final_url or str(page_rule.get("url", "")), str(link.get("href") or ""))
        try:
            detail_html, detail_url = fetch_detail(detail_url)
            duty = extract_detail_duty(detail_html)
        except Exception:
            continue
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "leader=a.tit[href*='/zrzy/content_']; duty=.conTxt 现任句",
            }
        )
    if not rows:
        raise RuntimeError("当前入口领导目录未解析出可验证人物和现任职务")
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
