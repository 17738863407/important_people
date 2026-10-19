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
    "rule_id": "3258", "page_type": "人物列表完整页", "structure_group": "sjz_medical_entry_to_leader_page_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "entry_to_list_page", "parser": "sjz_medical_entry_to_leader_page_v2",
    "leader_region_selector": "规则入口中链接文本为领导分工的导航 -> 子页#conN人物div",
    "name_selector": "人物div首个逗号前", "duty_selector": "首个逗号后至负责或分管关键词前",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "规则入口正文为机构简介，须动态跟随其领导分工导航；共享领导页不是独立人物详情页",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅合并网页排版空白，不改变原始职务或机构简称。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """从规则入口动态进入领导分工子页，并解析其人物职务行。"""
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    entry_soup = BeautifulSoup(html or "", "html.parser")
    leader_links = [
        link for link in entry_soup.select("a[href]")
        if clean_text(link.get_text(" ", strip=True)) == "领导分工"
    ]
    if len(leader_links) != 1:
        raise RuntimeError(f"领导分工导航链接数量异常：{len(leader_links)}")
    leader_url = urljoin(final_url, str(leader_links[0].get("href") or "").strip())
    leader_result = fetch_html_with_strategy(leader_url, strategy="online", timeout=40)
    soup = BeautifulSoup(leader_result.html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导分工正文数量异常：{len(regions)}")

    pattern = re.compile(
        r"^(?P<name>[\u3400-\u9fff·](?:\s*[\u3400-\u9fff·]){1,9})[，,]"
        r"(?P<duty>.+?)[，,](?P<responsibility>(?:负责|分管).+)[；;。]?$"
    )
    candidates = []
    for container in regions[0].find_all("div"):
        children = container.find_all("div", recursive=False)
        lines = [child for child in children if pattern.fullmatch(clean_text(child.get_text(" ", strip=True))) is not None]
        if len(lines) >= 2:
            candidates.append(lines)
    if len(candidates) != 1:
        raise RuntimeError(f"人物内容容器数量异常：{len(candidates)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for line in candidates[0]:
        text = clean_text(line.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if match is None:
            raise RuntimeError(f"人物分工行结构异常：{text}")
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = clean_text(match.group("duty"))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or name in seen_names:
            raise RuntimeError(f"人物姓名、职务异常或姓名重复：{name}")
        if line.select_one("a[href]") is not None:
            raise RuntimeError(f"人物分工行出现未审计链接：{name}")

        seen_names.add(name)
        records.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"],
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
