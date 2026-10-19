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
    "rule_id": "0399",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_finance_labeled_pairs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_finance_labeled_pairs_v2",
    "leader_region_selector": "#zoom",
    "name_selector": "姓名标签后的文本",
    "duty_selector": "职务标签后的文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名与职务既有分段也有同段排版，需按连续标签配对",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并正文中的排版空白。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([、，；：])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """在唯一正文内依次解析“姓名：… 职务：…”标签对。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#zoom")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    if regions[0].select_one("a[href]") is not None:
        raise RuntimeError("领导正文出现未审计链接")

    text = clean_text(regions[0].get_text(" ", strip=True))
    pattern = re.compile(r"姓名[:：](?P<name>.+?)职务[:：](?P<evidence>.+?)(?=姓名[:：]|$)")
    records: list[object] = []
    seen_names: set[str] = set()
    for match in pattern.finditer(text):
        name = re.sub(r"\s+", "", clean_text(match.group("name")))
        evidence = clean_text(match.group("evidence")).rstrip("。")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError(f"人物姓名或职务异常：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
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
        raise RuntimeError("领导正文没有可验证的姓名与职务标签对")
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
