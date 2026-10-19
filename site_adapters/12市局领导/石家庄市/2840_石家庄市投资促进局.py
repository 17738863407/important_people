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
    "rule_id": "2840", "page_type": "人物目录详情页", "structure_group": "sjz_investment_paging_detail_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "list_to_detail", "parser": "sjz_investment_paging_detail_v2",
    "leader_region_selector": "[id^=pagingCont_]内2至4字姓名链接",
    "name_selector": "分页区链接文本", "duty_selector": "详情#conN中姓名逗号后至冒号",
    "detail_link_selector": "[id^=pagingCont_] a[href]",
    "detail_strategy": {"required": True, "mode": "custom_parse_page", "detail_collector_type": "online", "max_detail_links": 20},
    "risk_flag": "分页区另含非人物职能设置条目；详情冒号后为分工、协助或暂无协助内容",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅合并网页排版空白，不改变详情页原始职务语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def extract_detail_evidence(html: str, name: str) -> str:
    """按详情正文中的姓名、逗号和冒号强边界提取完整原始职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"人物详情正文数量异常：{len(regions)}")
    text = clean_text(regions[0].get_text(" ", strip=True))
    match = re.fullmatch(rf"{re.escape(name)}[，,](?P<evidence>[^：:]+)[：:](?P<responsibility>.+)", text)
    if match is None:
        raise RuntimeError(f"人物详情姓名职务边界异常：{name} {text[:120]}")
    return re.sub(r"[（(]挂职[）)]", "", clean_text(match.group("evidence"))).rstrip("，、；; ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按分页区DOM顺序在线抓取人物详情并提取逗号、冒号之间的职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select('[id^="pagingCont_"]')
    if len(regions) != 1:
        raise RuntimeError(f"分页内容区数量异常：{len(regions)}")
    links = []
    for link in regions[0].select("a[href]"):
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name):
            links.append((link, name))
    if not links:
        raise RuntimeError("分页内容区没有人物姓名链接")

    records: list[object] = []
    seen_names: set[str] = set()
    for source_order, (link, name) in enumerate(links, start=1):
        href = str(link.get("href") or "").strip()
        if not href or name in seen_names:
            raise RuntimeError(f"人物目录链接为空或姓名重复：{name} {href}")
        detail_url = urljoin(final_url, href)
        detail_result = fetch_html_with_strategy(
            detail_url, strategy="online", timeout=40, request_attempt_offset=source_order,
        )
        evidence = extract_detail_evidence(detail_result.html, name)
        seen_names.add(name)
        records.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty=evidence, detail_url=detail_result.final_url or detail_url, evidence=evidence,
            confidence="high", parser=page_rule["parser"],
        ))
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
