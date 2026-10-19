from __future__ import annotations

import re
import sys
from pathlib import Path

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0102",
    "page_type": "人物表格页",
    "structure_group": "sz_audit_leader_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "extract_mode": "custom_parse_page",
    "parser": "sz_audit_leader_paragraphs_v2",
    "leader_region_selector": ".article-content",
    "name_selector": ".article-content p段首姓名",
    "duty_selector": ".article-content p姓名后的原始职务文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文每段为姓名加职务，首人职务以市委审计委员会办公室开头，不能限定为局名开头",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "api_config": {
        "url": "https://audit.sz.gov.cn/gkmlpt/api/all/373",
        "params": {"page": 1},
    },
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白并保留姓名与职务之间的结构分隔。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文段落顺序提取段首姓名和其后的原始职务文本。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    if not html:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
        config = page_rule["api_config"]
        api_response = session.get(config["url"], params=config["params"], timeout=30)
        api_response.raise_for_status()
        data = api_response.json()
        classify = data.get("classify") or {}
        articles = data.get("articles")
        if classify.get("id") != 373 or classify.get("name") != "机构领导":
            raise RuntimeError("机构领导分类接口身份异常")
        if not isinstance(articles, list) or len(articles) != 1:
            raise RuntimeError(f"机构领导分类接口文章数量异常：{len(articles or [])}")
        article_url = clean_text(str(articles[0].get("url") or ""))
        if not article_url.startswith("https://audit.sz.gov.cn/gkmlpt/content/"):
            raise RuntimeError("机构领导分类接口文章链接异常")
        article_response = session.get(article_url, timeout=30)
        article_response.raise_for_status()
        article_response.encoding = "utf-8"
        html = article_response.text

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("机构领导页缺少 .article-content")
    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in region.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.match(r"^([\u3400-\u9fff·]{2,10})\s+(.+)$", text)
        if match is None:
            continue
        name = match.group(1)
        evidence = clean_text(match.group(2))
        if "深圳市" not in evidence or "审计" not in evidence:
            raise RuntimeError(f"机构领导段落职务边界异常：{name}")
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
        raise RuntimeError("机构领导正文中未提取到人物段落")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
