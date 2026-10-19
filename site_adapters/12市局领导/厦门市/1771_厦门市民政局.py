from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1771",
    "page_type": "人物列表完整页",
    "structure_group": "xm_civil_affairs_division_notice_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_civil_affairs_division_notice_v2",
    "leader_region_selector": ".TRS_Editor .Custom_UnionStyle",
    "name_selector": "p中的序号后姓名",
    "duty_selector": "同一p姓名后的全角括号字段",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "冒号后是分工而非职务；只取姓名后的括号字段作为依据说明",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按通知段落顺序提取姓名与括号内原始职务。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到领导分工正文")
    pattern = re.compile(
        r"^[一二三四五六七八九十]+、\s*(?P<name>[\u3400-\u9fff·]{2,10})"
        r"（(?P<duty>[^）]+)）：(?P<division>.+)$"
    )
    records: list[object] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        line = clean_text(paragraph.get_text(" ", strip=True))
        match = pattern.match(line)
        if match is None:
            continue
        name = match.group("name")
        evidence = clean_text(match.group("duty"))
        if name in seen:
            raise RuntimeError(f"人物姓名重复：{name}")
        if not evidence:
            raise RuntimeError(f"人物缺少括号内职务：{name}")
        seen.add(name)
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
        raise RuntimeError("领导分工正文中未提取到人物")
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
