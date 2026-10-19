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
    "rule_id": "1765", "page_type": "人物目录详情页", "structure_group": "sjz_civil_affairs_title_links_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_civil_affairs_title_links_v2",
    "leader_region_selector": ".xxgknrws > div", "name_selector": "a标题末尾姓名",
    "duty_selector": "a标题中末尾姓名之前完整原文", "detail_link_selector": "a[href][target=_blank]",
    "detail_strategy": {"required": True, "mode": "list_dynamic"},
    "risk_flag": "原始职务已含机构名，不得删除",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按目录顺序从链接标题末尾姓名边界拆分完整原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    links = soup.select(".xxgknrws > div > a[href][target='_blank']")
    if not links:
        raise RuntimeError("领导目录没有找到人物链接")
    records: list[object] = []
    seen_names: set[str] = set()
    for link in links:
        title = clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[\u3400-\u9fff·]{2,10})", title)
        if match is None:
            raise RuntimeError(f"人物链接标题结构异常：{title}")
        name = match.group("name")
        evidence = clean_text(match.group("duty"))
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        if not evidence or not detail_url or detail_url == final_url or name in seen_names:
            raise RuntimeError(f"人物职务、详情链接异常或姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
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
