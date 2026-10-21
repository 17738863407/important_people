from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3169",
    "page_type": "多人物详情合并页",
    "structure_group": "yinchuan_commerce_titled_profile_blocks_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_commerce_titled_profile_blocks_v2",
    "leader_region_selector": ".zwxxgk_bd",
    "name_selector": "叶级人物标题段冒号前姓名",
    "duty_selector": "当前人物块简介段完整现任句",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".zwxxgk_bd"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": None, "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "每个人物标题后依次为简介和工作分工；仅在当前标题至下一标题范围内取完整现任句",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


TITLE_PATTERN = re.compile(r"^([\u4e00-\u9fff·\s]{2,8})\s*[:：]\s*[（(][^）)]+[）)]$")
CURRENT_DUTY_PATTERN = re.compile(r"现\s*任\s*[^。]*。")


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(value: str) -> str:
    """压缩正文中的全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物标题划分正文块并提取各自完整现任句。"""
    if not html:
        html, final_url = fetch_current_article(str(page_rule["url"]))
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector") or ""))
    if region is None:
        return []
    paragraphs = [_clean_text(node.get_text(" ", strip=True)) for node in region.select("p") if node.select_one("p") is None]
    paragraphs = [text for text in paragraphs if text]
    headers: list[tuple[int, re.Match[str]]] = []
    for index, text in enumerate(paragraphs):
        match = TITLE_PATTERN.fullmatch(text)
        if match is not None:
            headers.append((index, match))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for order, (start, match) in enumerate(headers):
        end = headers[order + 1][0] if order + 1 < len(headers) else len(paragraphs)
        name = "".join(match.group(1).split())
        block_text = _clean_text(" ".join(paragraphs[start + 1 : end]))
        evidence_match = CURRENT_DUTY_PATTERN.search(block_text)
        if evidence_match is None or name in seen:
            continue
        evidence = _clean_text(evidence_match.group(0)).removeprefix("现任").strip().removesuffix("。")
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser") or ""), "selector_summary": ".zwxxgk_bd内叶级人物标题p；当前标题至下一标题范围的完整现任句"})
    return rows


def derive_category_url(source_url: str) -> str:
    """从已失效的规则文章路径推导同站领导信息栏目。"""
    parts = urlsplit(source_url)
    category_path = re.sub(r"/\d{6}/t\d{8}_\d+\.html$", "/", parts.path)
    if category_path == parts.path:
        raise RuntimeError("规则入口不符合可验证的领导栏目文章路径")
    return urlunsplit((parts.scheme, parts.netloc, category_path, "", ""))


def fetch_current_article(source_url: str) -> tuple[str, str]:
    """在线发现领导栏目中的现行领导信息稿并取得正文。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    category_result = fetch_html_with_strategy(derive_category_url(source_url), strategy="requests")
    category_soup = BeautifulSoup(category_result.html, "html.parser")
    current_link = next(
        (
            link
            for link in category_soup.select(".zfxxgk_zdgkc > ul > li > a[href]")
            if "领导信息" in _clean_text(link.get_text(" ", strip=True))
        ),
        None,
    )
    if current_link is None:
        raise RuntimeError("领导栏目未发现现行领导信息稿")

    article_url = urljoin(category_result.final_url, str(current_link.get("href", "")))
    article_result = fetch_html_with_strategy(article_url, strategy="requests")
    return article_result.html, article_result.final_url


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
