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
    "rule_id": "3105",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_approval_leader_links_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_approval_leader_links_v2",
    "leader_region_selector": ".rightCon .pd20",
    "name_selector": "li > a[title]标题首段姓名",
    "duty_selector": "li > a[title]标题姓名后的完整原始职务",
    "detail_link_selector": "li > a[href]",
    "detail_strategy": {"required": True, "mode": "list_link"},
    "risk_flag": "姓名内可能含全角字距空格，人物职务之间的普通空格数量不一致",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并职务文本中的排版空白，不改变原始语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导列表链接的DOM顺序解析姓名、职务和独立详情页。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select(".rightCon .pd20")
    if len(regions) != 1:
        raise RuntimeError(f"领导区域数量异常：{len(regions)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for item in regions[0].select(":scope li"):
        links = item.select(":scope > a[href][title]")
        if len(links) != 1:
            raise RuntimeError(f"人物列表项链接数量异常：{len(links)}")
        link = links[0]
        title = str(link.get("title") or "").replace("\u3000", "").strip()
        match = re.fullmatch(r"(?P<name>[\u3400-\u9fff·]{2,10})\s+(?P<evidence>\S.*)", title)
        if match is None:
            raise RuntimeError(f"人物链接标题结构异常：{title}")
        name = match.group("name")
        evidence = clean_text(match.group("evidence"))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物职务异常或姓名重复：{name}")
        if not detail_url or detail_url == final_url:
            raise RuntimeError(f"人物详情链接异常：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导列表没有可验证人物链接")
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
