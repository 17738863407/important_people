from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2961",
    "page_type": "多人物详情合并页",
    "structure_group": "全国妇联现任领导列表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_women_current_leader_list_v2",
    "leader_region_selector": "#new_cont_0 ul.d_leader",
    "name_selector": "a[href]文本首部",
    "duty_selector": "a[href]文本姓名后部",
    "detail_link_selector": "a[href]",
    "risk_flag": "入口页同时是首位主席页面，等于入口的链接不得作为详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """统一页面排版空白，保留多个职务之间的原始先后关系。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_name_duty(value: str) -> tuple[str, str]:
    """以第一个明确职务关键词分割姓名与职务原文。"""
    text = clean_text(value)
    match = re.search(r"(党组书记|书记处第一书记|书记处书记|副主席|主席)", text)
    if not match:
        return "", ""
    name = re.sub(r"\s+", "", text[: match.start()])
    duty = clean_text(text[match.start() :])
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,20}", name):
        return "", ""
    return name, duty


def canonical_url(value: str) -> str:
    """移除片段并统一尾部斜杠，用于判断详情链接是否等于入口。"""
    parts = urlsplit(value)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按全国妇联现任领导列表DOM顺序抽取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#new_cont_0 ul.d_leader") or soup.select_one(".flld_r ul.d_leader")
    if region is None:
        raise RuntimeError("未定位到全国妇联现任领导列表")

    rows: list[dict] = []
    for link in region.select("a[href]"):
        name, duty = parse_name_duty(link.get_text(" ", strip=True))
        if not name or not duty:
            continue
        candidate = urljoin(final_url, str(link.get("href") or ""))
        detail_url = "" if canonical_url(candidate) == canonical_url(page_rule["url"]) else candidate
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_women_current_leader_list_v2",
                "selector_summary": (
                    "strategy=custom_parse_page；region=#new_cont_0 ul.d_leader；"
                    "item=a[href]；split=姓名后第一个明确职务关键词"
                ),
            }
        )
    if not rows:
        raise RuntimeError("全国妇联现任领导列表未抽取到人物")
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
