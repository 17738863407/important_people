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
    "rule_id": "2929",
    "page_type": "人物列表完整页",
    "structure_group": "wulumuqi_civil_affairs_numbered_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wulumuqi_civil_affairs_numbered_profiles_v2",
    "leader_region_selector": "#NewsContent .gjnr",
    "name_selector": "直属编号标题括号前姓名",
    "duty_selector": "直属编号标题括号内完整原始职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "每个人物标题后紧邻长篇职责段，职责不得并入主职务证据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并标题字段排版空白，不改变职务语义。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([、，；：])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按直属编号标题DOM顺序提取姓名和括号内原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#NewsContent .gjnr")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文区域数量异常：{len(regions)}")
    pattern = re.compile(
        r"^[一二三四五六七八九十]+、\s*"
        r"(?P<name>[\u3400-\u9fff·]{2,20})\s*[（(]\s*"
        r"(?P<evidence>[^）)]+)\s*[）)]\s*$"
    )

    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in regions[0].select(":scope > p"):
        raw_text = clean_text(paragraph.get_text(" ", strip=True))
        match = pattern.fullmatch(raw_text)
        if match is None:
            continue
        name = match.group("name")
        evidence = clean_text(match.group("evidence"))
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物职务异常或姓名重复：{name}")
        if paragraph.select_one("a[href]") is not None:
            raise RuntimeError(f"人物标题出现未审计链接：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导正文没有可验证编号人物标题")
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
