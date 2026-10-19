from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0602",
    "page_type": "人物表格页",
    "structure_group": "gd_gkmlpt_single_article_leader_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "gd_gkmlpt_single_article_leader_paragraphs_v2",
    "leader_region_selector": "机构领导分类接口唯一文章的.article-content",
    "name_selector": ".article-content p strong冒号前姓名",
    "duty_selector": ".article-content p冒号后原始职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "merged_article"},
    "api_config": {
        "url": "http://ga.sz.gov.cn/gkmlpt/api/all/783",
        "method": "GET",
        "params": {"page": 1, "sid": "755530"},
        "data_path": "articles",
        "detail_url_field": "url",
    },
    "risk_flag": "规则主表旧文章已404；同一权威平台分类接口指向当前合并领导页，合并页不能作为个人详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML与接口字段中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def http_fetch_url(value: str) -> str:
    """使用同站HTTP地址获取当前合并文章。"""
    parts = urlsplit(value)
    return urlunsplit(("http", parts.netloc, parts.path, parts.query, ""))


def fetch_current_article(session: requests.Session, page_rule: dict) -> str:
    """从机构领导分类接口动态发现并获取当前唯一合并文章。"""
    config = page_rule["api_config"]
    response = session.get(config["url"], params=config["params"], timeout=30)
    response.raise_for_status()
    data = response.json()
    classify = data.get("classify") or {}
    articles = data.get(config["data_path"])
    if classify.get("id") != 783 or classify.get("name") != "机构领导":
        raise RuntimeError("分类接口返回的栏目身份与机构领导不一致")
    if data.get("total") != 1 or not isinstance(articles, list) or len(articles) != 1:
        raise RuntimeError("机构领导分类接口并非唯一合并文章")
    item = articles[0]
    if clean_text(str(item.get("title") or "")) != "机构领导":
        raise RuntimeError("机构领导分类接口文章标题异常")
    detail_url = clean_text(str(item.get(config["detail_url_field"]) or ""))
    if not detail_url.startswith("https://ga.sz.gov.cn/gkmlpt/content/"):
        raise RuntimeError("机构领导分类接口文章链接异常")
    detail = session.get(http_fetch_url(detail_url), timeout=30)
    detail.raise_for_status()
    detail.encoding = "utf-8"
    return detail.text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按当前合并文章段落顺序提取姓名和冒号后的原始职务。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    soup = BeautifulSoup(fetch_current_article(session, page_rule), "html.parser")
    article = soup.select_one(".article-content")
    if article is None:
        raise RuntimeError("当前机构领导文章缺少 .article-content")
    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in article.select("p"):
        if paragraph.select_one("strong") is None:
            continue
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.match(r"^(.+?)[：:]\s*(.+)$", text)
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        evidence = clean_text(match.group(2))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("领导段落姓名或职务结构异常")
        if name in seen_names:
            raise RuntimeError(f"机构领导姓名重复：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("当前机构领导合并文章中未提取到人物")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.runner import (
        build_selector_summary,
        normalize_inline_rows,
        normalize_record_source_urls,
        prepare_records_for_export,
        safe_filename,
    )

    page_rule = apply_business_source(dict(PAGE_RULE))
    rows = normalize_inline_rows(
        page_rule,
        parse_page("", str(page_rule["url"]), page_rule),
    )
    normalize_record_source_urls(page_rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        row.script_sequence = normalize_script_sequence(page_rule["rule_id"])
        if not row.selector_summary:
            row.selector_summary = build_selector_summary(page_rule)
    output_name = (
        f"{page_rule['rule_id']}_{safe_filename(page_rule['page_type'])}_"
        f"{safe_filename(page_rule['load_mode'])}_{safe_filename(page_rule['organization'])}.txt"
    )
    output_path = project_dir / "outputs" / output_name
    export_records(output_path, rows)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
