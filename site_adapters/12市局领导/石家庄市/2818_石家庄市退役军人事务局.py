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
    "rule_id": "2818", "page_type": "人物目录详情页", "structure_group": "sjz_veterans_grouped_directory_detail_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "list_to_detail", "parser": "sjz_veterans_grouped_directory_detail_v2",
    "leader_region_selector": "标题为领导介绍的分组 .xxgknrws a[href]",
    "name_selector": "领导介绍分组链接文本", "duty_selector": "详情.ldjgxx内完整现任句",
    "detail_link_selector": "领导介绍分组 .xxgknrws a[href]",
    "detail_strategy": {"required": True, "mode": "custom_parse_page", "detail_collector_type": "online", "max_detail_links": 20},
    "risk_flag": "入口同页另有机构职责、机构信息、内设机构、所属机构和其他机构分组，必须只取领导介绍",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅合并网页排版空白，不改变详情页现任原句。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def extract_current_sentence(html: str) -> str:
    """只在当前人物详情最小容器内提取完整现任句。"""
    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select(".ldjgxx")
    if len(regions) != 1:
        raise RuntimeError(f"人物详情容器数量异常：{len(regions)}")
    text = clean_text(regions[0].get_text(" ", strip=True))
    matches = re.findall(r"现任[^。]*。", text)
    if len(matches) != 1:
        raise RuntimeError(f"人物详情现任句数量异常：{len(matches)}")
    return re.sub(r"^现任\s*", "", clean_text(matches[0])).rstrip("。")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """只遍历领导介绍分组，并按目录顺序在线抓取每个人物详情。"""
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    leader_sections = []
    for section in soup.select(".xxgknrws"):
        title = section.parent.select_one(".ztljsdwq") if section.parent is not None else None
        if title is not None and clean_text(title.get_text(" ", strip=True)) == "领导介绍":
            leader_sections.append(section)
    if len(leader_sections) != 1:
        raise RuntimeError(f"领导介绍分组数量异常：{len(leader_sections)}")

    links = leader_sections[0].select("a[href]")
    if not links:
        raise RuntimeError("领导介绍分组没有人物链接")
    records: list[object] = []
    seen_names: set[str] = set()
    for source_order, link in enumerate(links, start=1):
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not href or name in seen_names:
            raise RuntimeError(f"人物目录姓名、链接异常或姓名重复：{name} {href}")
        detail_url = urljoin(final_url, href)
        detail_result = fetch_html_with_strategy(
            detail_url, strategy="online", timeout=40, request_attempt_offset=source_order,
        )
        evidence = extract_current_sentence(detail_result.html)
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
