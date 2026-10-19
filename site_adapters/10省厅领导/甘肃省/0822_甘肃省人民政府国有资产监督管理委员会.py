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
    "rule_id": "0822",
    "page_type": "人物列表完整页",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "parser": "page_parse_page",
    "leader_region_selector": "#container .xxgk_box",
    "name_selector": 'a[href^="/gzw/c108987/"][href$=".shtml"]',
    "duty_selector": ".links_words #content p",
    "detail_link_selector": 'a[href^="/gzw/c108987/"][href$=".shtml"]',
    "detail_strategy": {"required": True, "mode": "person_name_link"},
    "risk_flag": "普通HTTP返回412且Playwright为空页，online最终使用Chrome CDP；详情只取人物简介首段现任句",
    "confidence": "high",
    "filter_policy": "weak_allow_wordlist",
    "locator_strategy": "custom_parse_page",
    "risk_note": "名单链接限定领导栏目路径；详情标题必须包含列表姓名，主持、负责、分管等后续职责段不进入依据。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """动态遍历领导名单，并从每个人物详情首段提取完整现任职务句。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    selector = '#container .xxgk_box a[href^="/gzw/c108987/"][href$=".shtml"]'
    for link in soup.select(selector):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_result = fetch_html_with_strategy(
            urljoin(final_url, str(link.get("href", ""))),
            "chrome",
        )
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        title = detail_soup.title.get_text(" ", strip=True) if detail_soup.title else ""
        if name not in title:
            raise ValueError(f"领导详情标题与列表姓名不一致：{name}")
        intro = ""
        for intro_node in detail_soup.select(".links_words #content p"):
            candidate = re.sub(r"\s+", " ", intro_node.get_text(" ", strip=True)).strip()
            if name in candidate and "现任" in candidate:
                intro = candidate
                break
        duty_match = re.search(r"现任[^。]*。", intro)
        if duty_match is None:
            raise ValueError(f"领导详情首段缺少现任职务句：{name}")
        evidence = re.sub(r"^现任\s*", "", duty_match.group(0))
        evidence = re.sub(r"\s*([、，；：])\s*", r"\1", evidence)
        evidence = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", evidence)
        evidence = evidence.rstrip("。 ")
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_result.final_url,
                "evidence": evidence,
                "parser": "page_parse_page",
                "selector_summary": "列表=#container .xxgk_box领导详情链接；详情=.links_words #content人物简介现任句",
            }
        )
    if not rows:
        raise ValueError("当前领导栏目未发现可验证人物详情链接")
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
