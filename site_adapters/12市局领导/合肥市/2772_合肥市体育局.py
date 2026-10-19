from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "2772",
    "page_type": "人物目录详情页",
    "structure_group": "hefei_sports_public_detail",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "browser_render_wait_ms": 8000,
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "directory_detail",
    "collector": "browser_dom",
    "parser": "hefei_sports_public_detail_v1",
    "leader_region_selector": "#xxgk_lmcon table.xxgk-table-list > tbody > tr",
    "name_selector": "#zoom p",
    "duty_selector": "#xxgk_lmcon table.xxgk-table-list a[href]",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "栏目与详情需浏览器渲染；姓名由详情核验，职务取栏目强结构标题前缀",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """合并网页排版空白，不改写非空白字符。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _compact_text(value: str) -> str:
    """移除字段内部的纯排版空白，用于回指被拆字的网页文本。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value)


def _validate_detail_url(href: str, entry_url: str) -> str:
    """只接受当前政务公开栏目中的同域人物详情地址。"""
    detail_url = urljoin(entry_url, href)
    entry = urlparse(entry_url)
    detail = urlparse(detail_url)
    if detail.netloc != entry.netloc:
        return ""
    if not re.fullmatch(r"/public/20201/\d+\.html", detail.path):
        return ""
    return detail_url


def _extract_detail_name(detail_html: str) -> str:
    """从详情正文的个人简历段提取姓名，并与详情标题互证。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    title = soup.select_one("h1")
    region = soup.select_one("#zoom")
    if title is None or region is None:
        return ""

    title_text = _compact_text(title.get_text(" ", strip=True))
    matches: list[str] = []
    for paragraph in region.select("p"):
        text = _compact_text(_clean_text(paragraph.get_text(" ", strip=True)))
        profile_match = re.match(r"^(?P<name>[一-鿿·]{2,8})[，,]", text)
        if not profile_match:
            continue
        name = profile_match.group("name")
        if title_text.endswith(name):
            matches.append(name)
    if len(matches) != 1:
        return ""
    return matches[0]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按栏目表格顺序动态发现并在线核验人物详情。"""
    from crawler_core.fetcher import fetch_by_playwright
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(page_rule["leader_region_selector"])
    if not rows:
        raise RuntimeError("机构领导表格行选择器未命中")

    records: list[object] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for source_order, row in enumerate(rows, start=1):
        link = row.select_one(page_rule["detail_link_selector"])
        detail_url = _validate_detail_url(str(link.get("href", "")) if link else "", final_url)
        if not detail_url or detail_url in seen_urls:
            raise RuntimeError(f"第 {source_order} 个详情链接无效或重复")

        detail_result = fetch_by_playwright(detail_url, timeout=60)
        name = _extract_detail_name(detail_result.html)
        list_text = _compact_text(link.get_text(" ", strip=True))
        if not name or not list_text.endswith(name):
            raise RuntimeError(f"第 {source_order} 个详情姓名无法回指栏目标题")
        duty = list_text[: -len(name)]
        if not re.fullmatch(r"[一-鿿、，,（）：:·]{1,40}", duty):
            raise RuntimeError(f"第 {source_order} 个栏目职务前缀无效：{duty or '空'}")
        if not duty or name in seen_names:
            raise RuntimeError(f"第 {source_order} 个详情职务为空或姓名重复：{name or '空'}")
        if not _validate_detail_url(detail_result.final_url, final_url):
            raise RuntimeError(f"第 {source_order} 个详情最终地址不符合栏目路径")

        seen_names.add(name)
        seen_urls.add(detail_url)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_result.final_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
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
