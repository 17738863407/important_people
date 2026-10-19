from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0761",
    "page_type": "人物列表完整页",
    "structure_group": "leader_index_latest_article_strong_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "栏目页转最新静态文章",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".article_con p",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".article_con"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "文章编号会更新，须从栏目动态进入最新领导分工；姓名与职务可能分布在多个strong节点中",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文顺序解析姓名职务段落，不采集后续职责分工。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one(".article_con") is None:
        article_link = next(
            (
                link
                for link in soup.select("a[href]")
                if re.sub(r"\s+", "", link.get_text(" ", strip=True))
                == "广州市工业和信息化局领导分工"
                and str(link.get("href") or "").endswith(".html")
            ),
            None,
        )
        if article_link is None:
            raise RuntimeError("领导简介栏目未找到最新领导分工文章")
        article_url = urljoin(final_url or page_rule["url"], str(article_link.get("href") or ""))
        article = fetch_html_with_strategy(article_url, "raw_http")
        soup = BeautifulSoup(article.html, "html.parser")
    duty_start_pattern = re.compile(
        r"^(?P<name>[\u4e00-\u9fff]{2,4})"
        r"(?P<duty>市管一级调研员|党组书记.*|党组成员.*|二级巡视员.*)$"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for paragraph in soup.select(".article_con p"):
        if not paragraph.select_one("strong"):
            continue
        compact = re.sub(
            r"[\s\u3000\xa0]+", "", paragraph.get_text(" ", strip=True)
        ).strip("，,。；;：:")
        if not compact or "职责分工" in compact:
            continue
        match = duty_start_pattern.fullmatch(compact)
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty").strip("，,。；;：:")
        if name in seen:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": ".article_con p strong姓名职务段落",
            }
        )
        seen.add(name)

    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
