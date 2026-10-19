from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2897",
    "page_type": "人物目录详情页",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "parser": "page_parse_page",
    "leader_region_selector": "#barrierfree_container .w1100.center",
    "name_selector": 'a[href^="/col/col9273"][href$="/index.html"]',
    "duty_selector": ".bt_content",
    "detail_link_selector": 'a[href^="/col/col9273"][href$="/index.html"]',
    "detail_strategy": {"required": True, "mode": "person_name_link"},
    "risk_flag": "详情简介后可能紧随主持职责，依据只取姓名开头的第一完整职务句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "risk_note": "仅遍历当前局领导目录人物链接；详情标题校验姓名，个人简介首句之后的主持/分工不纳入依据。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按局领导目录原序读取详情，并截取个人简介第一完整职务句。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    selector = '#barrierfree_container a[href^="/col/col9273"][href$="/index.html"]'
    for link in soup.select(selector):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")))
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        detail_result = fetch_html_with_strategy(detail_url, "requests")
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        title = re.sub(r"\s+", "", detail_soup.title.get_text(" ", strip=True) if detail_soup.title else "")
        if name not in title:
            raise ValueError(f"领导详情标题与列表姓名不一致：{name}")
        intro_node = detail_soup.select_one(".bt_content")
        intro = re.sub(r"\s+", " ", intro_node.get_text(" ", strip=True) if intro_node else "").strip()
        intro = re.sub(r"^个人简介\s*", "", intro)
        sentence_match = re.match(rf"{re.escape(name)}\s*[，,]\s*[^。]+。", re.sub(r"\s+", "", intro))
        if sentence_match is None:
            raise ValueError(f"领导详情缺少姓名开头的完整职务句：{name}")
        evidence = re.sub(rf"^{re.escape(name)}\s*[，,]\s*", "", sentence_match.group(0)).strip(" ，,。；;：: ")
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_result.final_url,
                "evidence": evidence,
                "parser": "page_parse_page",
                "selector_summary": "列表=局领导目录人物链接；详情=.bt_content个人简介第一句",
            }
        )
    if not rows:
        raise ValueError("局领导目录未发现可验证人物链接")
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
