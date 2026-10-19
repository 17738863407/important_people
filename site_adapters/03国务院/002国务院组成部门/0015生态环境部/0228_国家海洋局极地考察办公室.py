from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0228",
    "page_type": "人物列表完整页",
    "structure_group": "chinare_principal_leaders_static_list_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "requests",
    "parser": "builtin_parse_page",
    "leader_region_selector": "div.list-item",
    "name_selector": "a[href^='/contents/7/']标题末尾姓名",
    "duty_selector": "a标题中姓名前原文",
    "detail_link_selector": "a[href^='/contents/7/']",
    "detail_strategy": {"required": False, "mode": "list_links"},
    "risk_flag": "页面标题采用职务在前、姓名在后的格式，须以末尾姓名边界切分",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """只清理接口HTML中的排版空白。"""
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按主要负责人列表的网页顺序提取标题、姓名与详情页。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    records: list[PersonRecord] = []
    seen_urls: set[str] = set()
    for link in soup.select("div.list-item a[href]"):
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"/contents/7/\d+\.html", href):
            continue
        detail_url = urljoin(final_url or page_rule["url"], href)
        if detail_url in seen_urls:
            continue
        title = _clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[\u3400-\u9fff·]{2,6})", title)
        if match is None:
            continue
        duty = _clean_text(match.group("duty"))
        name = match.group("name")
        seen_urls.add(detail_url)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="主要负责人列表div.list-item中的详情标题与链接",
            )
        )
    if not records:
        raise RuntimeError("主要负责人列表没有有效人物记录")
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
