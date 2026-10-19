from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2735",
    "domain": "tjj.ln.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_directory_detail_labeled_role_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_leader_directory_detail_labeled_role_v1",
    "leader_region_selector": "ul.provincial-leaders-inner",
    "detail_link_selector": "dd.ldname a[istitle='true'][href]",
    "detail_name_selector": ".xxgk_ldlxm",
    "detail_content_selector": ".xxgk_ldr",
    "detail_strategy": {"required": True, "mode": "list_to_detail_labeled_field"},
    "risk_flag": "详情同容器还含工作分工；职务证据仅取独立“职务：”段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩字段中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def extract_labeled_duty(container: object) -> str:
    """从当前人物详情容器的独立“职务：”段落提取原始职务。"""
    if not hasattr(container, "select"):
        return ""
    for paragraph in container.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"职务\s*[：:]\s*(.+)", text)
        if match:
            return clean_text(match.group(1))
    return ""


def fetch_detail_duty(
    detail_url: str,
    expected_name: str,
    page_rule: dict[str, object],
    attempt_offset: int,
) -> str:
    """在线读取详情姓名并提取带标签的职务强字段。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    soup = BeautifulSoup(result.html, "html.parser")
    name_node = soup.select_one(str(page_rule.get("detail_name_selector", "")))
    content_node = soup.select_one(str(page_rule.get("detail_content_selector", "")))
    if name_node is None or content_node is None:
        return ""
    if clean_name(name_node.get_text(" ", strip=True)) != expected_name:
        return ""
    return extract_labeled_duty(content_node)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口领导目录顺序抓取各详情页的原始职务字段。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    selector = str(page_rule.get("detail_link_selector", ""))
    for source_order, link in enumerate(region.select(selector), start=1):
        name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not href or name in seen:
            continue
        detail_url = urljoin(final_url or source_url, href)
        try:
            duty = fetch_detail_duty(detail_url, name, page_rule, source_order)
        except Exception:
            continue
        if not duty:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=ul.provincial-leaders-inner "
                    "dd.ldname a[istitle=true]；detail name=.xxgk_ldlxm；"
                    "duty=.xxgk_ldr p label=职务"
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
