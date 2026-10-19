from __future__ import annotations

import json
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
    "rule_id": "1462",
    "domain": "ly.jiangxi.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jiangxi_forestry_parent_children_article_tags_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "channel_metadata_direct",
    "collector": "static_http",
    "parser": "page_inline_jiangxi_forestry_parent_children_article_tags_v2",
    "detail_strategy": {"required": True, "mode": "dynamic_child_channel"},
    "risk_flag": "页面展示DOM为空；顺序取父频道children；站点HTTPS旧式协商偶发失败，内部子页用HTTP读取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML与元数据中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def compact_name(value: str) -> str:
    """移除姓名中的排版空白和HTML标签。"""
    text = BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", "", clean_text(text))


def extract_leader_children(html: str) -> list[dict[str, object]]:
    """从当前人物页父频道元数据读取可见领导子频道数组顺序。"""
    match = re.search(
        r"var\s+channelsTagParent\s*=\s*\[\s*(\{.*?\})\s*,?\s*\]\s*//父级栏目信息",
        html,
        flags=re.S,
    )
    if match is None:
        return []
    try:
        parent = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    children = parent.get("children", [])
    return [child for child in children if isinstance(child, dict)]


def force_http(value: str) -> str:
    """站点HTTPS旧式协商不稳定，内部只读采集改用同址HTTP。"""
    parts = urlsplit(value)
    return urlunsplit(("http", parts.netloc, parts.path, parts.query, parts.fragment))


def fetch_child_article(child_url: str, attempt_offset: int) -> dict[str, object]:
    """在线读取人物子频道索引页内嵌的唯一articleTag记录。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(force_http(child_url), timeout=40, attempt_offset=attempt_offset)
    match = re.search(r"var\s+articleTag\s*=\s*", result.html)
    if match is None:
        return {}
    payload = result.html[match.end() :].lstrip()
    try:
        articles, _ = json.JSONDecoder().raw_decode(payload)
    except json.JSONDecodeError:
        return {}
    if not isinstance(articles, list) or not articles or not isinstance(articles[0], dict):
        return {}
    return articles[0]


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按父频道children顺序提取人物子频道articleTag的姓名、职务和详情。"""
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, child in enumerate(extract_leader_children(html), start=1):
        listed_name = compact_name(str(child.get("name") or child.get("showName") or ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", listed_name) or listed_name in seen:
            continue
        try:
            child_url_data = json.loads(str(child.get("urls", "{}")))
        except json.JSONDecodeError:
            continue
        child_path = str(child_url_data.get("pc", ""))
        if not child_path:
            continue
        child_url = urljoin(source_url, child_path)
        try:
            article = fetch_child_article(child_url, source_order)
        except Exception:
            continue
        title = compact_name(str(article.get("title", "")))
        duty = clean_text(str(article.get("summary", ""))).strip(" ：:，,；;。 ")
        if not title.startswith(listed_name) or not duty:
            continue
        try:
            detail_url_data = json.loads(str(article.get("urls", "{}")))
        except json.JSONDecodeError:
            continue
        detail_path = str(detail_url_data.get("pc", ""))
        if not detail_path:
            continue
        seen.add(listed_name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": listed_name,
                "duty": duty,
                "detail_url": urljoin(source_url, detail_path),
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；order=channelsTagParent[0].children；"
                    "child=articleTag[0]；name=child-name-cross-check-title；"
                    "duty=summary；detail=urls.pc"
                ),
            }
        )

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
