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
    "rule_id": "0361",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "profile_blocks",
    "parser": "beijing_finance_profile_blocks_v3",
    "leader_region_selector": ".ul-back div[class^='ldjl-']",
    "name_selector": "img[alt][title]",
    "duty_selector": "p.pp1当前人物块内完整现任首句",
    "detail_link_selector": "",
    "locator_strategy": "custom_parse_page",
    "filter_policy": "strong_no_wordlist",
    "confidence": "high",
    "risk_flag": "同块含主持、分管、联系信息，仅提取完整现任首句",
}


def _clean_text(value: object) -> str:
    """仅清理HTML排版空白，不改写原文语义和标点。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物块DOM顺序提取图片姓名及当前块完整“现任……”首句。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for block in soup.select(page_rule["leader_region_selector"]):
        image = block.select_one("img[alt]")
        text_node = block.select_one("p.pp1")
        name = re.sub(r"\s+", "", _clean_text(image.get("alt") if image else ""))
        block_text = _clean_text(text_node.get_text(" ", strip=True) if text_node else "")
        sentence_match = re.search(r"现任[^。]*。", block_text)
        evidence = (
            re.sub(r"^现任\s*", "", sentence_match.group(0)).removesuffix("。").strip()
            if sentence_match
            else ""
        )
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not evidence or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence=page_rule["confidence"],
                parser=page_rule["parser"],
            )
        )
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
