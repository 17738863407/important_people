from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean_text(value: str) -> str:
    """压缩 HTML 文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析湖南省公安厅领导之窗首页领导卡片。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    source_url = str(page_rule.get("url", ""))
    base_url = final_url or source_url
    seen: set[str] = set()

    def normalize_detail_url(href: str) -> str:
        href = str(href or "").strip()
        detail_url = urljoin(base_url, href) if href else ""
        parsed_detail = urlparse(detail_url)
        if (
            not href
            or href.startswith(('#', 'javascript:'))
            or parsed_detail.netloc.lower() != urlparse(base_url).netloc.lower()
            or urldefrag(detail_url)[0].rstrip('/') == urldefrag(base_url)[0].rstrip('/')
            or not parsed_detail.path.lower().endswith(('.shtml', '.html', '.htm'))
        ):
            return ""
        return detail_url

    def parse_detail_duty(detail_url: str) -> str:
        if not detail_url:
            return ""
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="requests", timeout=30)
        except Exception:
            return ""
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        text = clean_text(detail_soup.get_text(" ", strip=True))
        match = re.search(r"现任职务\s*[:：]\s*(?P<duty>.+?)\s*(?:工作分工|个人简历)\s*[:：]", text)
        if not match:
            return ""
        return clean_text(match.group("duty")).strip(" ：:，,。.；;")

    big_leader = soup.select_one(".MainContainer .BigLeader")
    if big_leader:
        name = clean_text(big_leader.select_one(".LeaderIntroduction h2").get_text(" ", strip=True)) if big_leader.select_one(".LeaderIntroduction h2") else ""
        duty = clean_text(big_leader.select_one(".LeaderIntroduction p").get_text(" ", strip=True)) if big_leader.select_one(".LeaderIntroduction p") else ""
        link = big_leader.select_one("a.LeaderButton[href], a.BigLeaderPic[href]")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) and duty:
            detail_url = normalize_detail_url(str(link.get("href") or "")) if link else ""
            detail_duty = parse_detail_duty(detail_url)
            seen.add(name)
            rows.append(
                {
                    "organization": str(page_rule.get("organization", "")),
                    "url": source_url,
                    "name": name,
                    "duty": detail_duty or duty,
                    "detail_url": detail_url,
                    "evidence": detail_duty or duty,
                    "confidence": "high",
                    "parser": "page_detail_hunan_police_leader_v1",
                }
            )

    for item in soup.select(".MainContainer .LeaderOther li"):
        link = item.select_one("p a[href]")
        name = clean_text(link.get_text(" ", strip=True)) if link else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = normalize_detail_url(str(link.get("href") or ""))
        duty = parse_detail_duty(detail_url)
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high" if duty else "medium",
                "parser": "page_detail_hunan_police_leader_v1",
            }
        )
    return rows


PAGE_RULE = {'rule_id': '0631',
 'domain': 'gat.hunan.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '接口数据加载',
        'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_inline_hunan_police_leader_window_v1',
 'leader_region_selector': '.MainContainer .BigLeader, .MainContainer .LeaderOther li',
 'name_selector': '.LeaderIntroduction h2, .LeaderOther li p a[href]',
 'duty_selector': '.LeaderIntroduction p',
 'detail_link_selector': '.BigLeader a[href], .LeaderOther li p a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False, 'mode': 'custom_inline_fetch_detail'},
 'risk_flag': '',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.MainContainer .BigLeader, .MainContainer .LeaderOther li',
                     'name_selector': '.LeaderIntroduction h2, .LeaderOther li p a[href]',
                     'duty_selector': '.LeaderIntroduction p',
                     'detail_link_selector': '.BigLeader a[href], .LeaderOther li p a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面使用原 DOM 定位并逐人抓取详情职务'}}}


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
