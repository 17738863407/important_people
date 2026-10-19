from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "2260",
    "page_type": "多人物详情合并页",
    "structure_group": "xiamen_market_supervision_profile_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "xiamen_market_supervision_profile_paragraphs_v2",
    "leader_region_selector": "div.TRS_Editor > div.TRS_Editor",
    "name_selector": "p",
    "duty_selector": "p",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "仅配对人物标题段与下一非空现任简介段，分组标题和分工段不参与",
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
    """移除现任句中的纯排版空白，修复网页拆字但不补写字符。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文顺序解析人物标题及其紧邻的现任简介段。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导正文命中数量异常：{len(regions)}")
    lines = [
        _clean_text(paragraph.get_text(" ", strip=True))
        for paragraph in regions[0].select("p")
    ]
    lines = [line for line in lines if line]

    records: list[object] = []
    seen_names: set[str] = set()
    for index in range(len(lines) - 1):
        heading = lines[index]
        profile = _compact_text(lines[index + 1])
        heading_parts = heading.split(maxsplit=1)
        if len(heading_parts) != 2:
            continue
        name = heading_parts[0]
        if not re.fullmatch(r"[一-鿿·]{2,8}", name):
            continue
        duty_match = re.search(r"现任[^。]*。", profile)
        if duty_match is None:
            continue
        duty = duty_match.group(0).removeprefix("现任").removesuffix("。").rstrip()
        if name in seen_names or len(duty) > 160:
            raise RuntimeError(f"姓名重复或现任句异常：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导正文未解析到人物现任记录")
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
