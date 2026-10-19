from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2939",
    "page_type": "机构入口转领导正文页",
    "structure_group": "wulumuqi_department_portal_leader_article",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_article",
    "collector": "static_http",
    "parser": "page_inline_wulumuqi_justice_name_colon_duty_v2",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "入口页机构简介中的领导班子成员信息链接",
    "name_selector": "#NewsContent .gjnr p 段首冒号前姓名",
    "duty_selector": "#NewsContent .gjnr p 段首冒号后职务",
    "detail_link_selector": "",
    "risk_flag": "规则主表为机构入口，须动态跟随当前领导文章；文章内简历段落不得并入职务",
    "confidence": "high",
}


def _clean_text(value: str) -> str:
    text = " ".join(value.split())
    text = text.replace("\u3000", "")
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"\s+([、，；：])", r"\1", text)
    text = re.sub(r"([、，；：])\s+(?=[\u4e00-\u9fff])", r"\1", text)
    text = re.sub(r"\s*([（）])\s*", r"\1", text)
    return text.strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析乌鲁木齐市司法局领导班子成员信息。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    entrance = BeautifulSoup(html, "lxml")
    article_link = next(
        (
            anchor
            for anchor in entrance.select("a[href]")
            if "司法局领导班子成员信息" in _clean_text(anchor.get_text(" ", strip=True))
        ),
        None,
    )
    if article_link is None:
        raise RuntimeError("机构入口未找到当前司法局领导班子成员信息链接")
    article_url = urljoin(final_url, str(article_link.get("href", "")))
    entrance_host = urlsplit(final_url).netloc
    article_parts = urlsplit(article_url)
    if article_parts.netloc != entrance_host or not re.fullmatch(
        r"/wlmqs/c119172/\d{6}/[0-9a-f]+\.shtml",
        article_parts.path,
    ):
        raise RuntimeError("领导文章链接不符合机构简介栏目结构")
    article_result = fetch_by_raw_requests(article_url, timeout=30)
    soup = BeautifulSoup(article_result.html, "lxml")
    paragraphs = [_clean_text(p.get_text(" ", strip=True)) for p in soup.select("#NewsContent .gjnr p")]
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for text in paragraphs:
        match = re.match(r"^([\u4e00-\u9fff]{2,4})[:：]\s*(.+)$", text)
        if not match:
            continue
        name = _clean_text(match.group(1))
        duty = _clean_text(match.group(2))
        if not name or not duty or len(name) > 4:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": page_rule.get("parser", ""),
            }
        )
    if not records:
        raise RuntimeError("领导文章未解析出有效的姓名与职务段落")
    return records


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

