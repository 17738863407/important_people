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
    "rule_id": "1230",
    "page_type": "人物目录详情页",
    "structure_group": "hefei_transport_ld_y_detail",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "browser_render_wait_ms": 8000,
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "directory_detail",
    "collector": "browser_dom",
    "parser": "hefei_transport_ld_y_detail_v1",
    "leader_region_selector": "#xxgk_lmcon .inner-list .page-list .xxgk-tab-content table.xxgk-table-list > tbody > tr",
    "name_selector": "#zoom p",
    "duty_selector": "#zoom p",
    "detail_link_selector": "td.title-td > a.title[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "栏目页 ld_y 为首人公共预览，不作为详情证据；仅解析详情 #zoom 的姓名段和现任段",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅清理网页排版空白，不改写语义内容。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _extract_detail_fields(detail_html: str) -> tuple[str, str]:
    """取得详情正文的姓名段和完整现任职务段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    region = soup.select_one("#zoom")
    if region is None:
        return "", ""

    names: list[str] = []
    current_duties: list[str] = []
    lines = [_clean_text(line) for line in region.get_text("\n", strip=True).splitlines()]
    for text in [line for line in lines if line]:
        name_match = re.match(r"^(?P<name>[一-鿿·\s]{2,12})[，,]", text)
        if name_match:
            name = re.sub(r"\s+", "", name_match.group("name"))
            if re.fullmatch(r"[一-鿿·]{2,8}", name):
                names.append(name)
        if re.fullmatch(r"现任[：:][^。]+。", text):
            current_duties.append(re.sub(r"^现任[：:]", "", text).removesuffix("。"))
    if len(names) != 1 or len(current_duties) != 1:
        return "", ""
    return names[0], current_duties[0]


def _validate_detail_url(href: str, final_url: str) -> str:
    """只接受栏目当前行提供的同域人物详情地址。"""
    detail_url = urljoin(final_url, href)
    entry = urlparse(final_url)
    detail = urlparse(detail_url)
    if detail.netloc != entry.netloc:
        return ""
    if not re.fullmatch(r"/public/7451/\d+\.html", detail.path):
        return ""
    return detail_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按栏目 DOM 顺序在线解析每个独立人物详情页。"""
    from crawler_core.fetcher import fetch_by_playwright
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(page_rule["leader_region_selector"])
    if not rows:
        raise RuntimeError("机构领导栏目表格选择器未命中")

    records: list[object] = []
    seen_names: set[str] = set()
    for source_order, row in enumerate(rows, start=1):
        link = row.select_one(page_rule["detail_link_selector"])
        detail_url = _validate_detail_url(str(link.get("href", "")) if link else "", final_url)
        if not detail_url:
            raise RuntimeError(f"第 {source_order} 个栏目详情链接无效")

        list_name = re.sub(r"\s+", "", _clean_text(link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[一-鿿·]{2,8}", list_name):
            raise RuntimeError(f"第 {source_order} 个栏目姓名无效：{list_name or '空'}")
        detail_result = fetch_by_playwright(detail_url, timeout=60)
        detail_name, duty = _extract_detail_fields(detail_result.html)
        if detail_name != list_name:
            raise RuntimeError(
                f"第 {source_order} 个详情姓名不一致：栏目={list_name}，详情={detail_name or '空'}"
            )
        if not duty or detail_name in seen_names:
            raise RuntimeError(f"第 {source_order} 个详情职务为空或姓名重复：{detail_name}")
        if not _validate_detail_url(detail_result.final_url, final_url):
            raise RuntimeError(f"第 {source_order} 个详情最终地址不符合栏目路径")

        seen_names.add(detail_name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=detail_name,
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
