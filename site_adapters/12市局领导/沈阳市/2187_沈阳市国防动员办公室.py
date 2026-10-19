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
    "rule_id": "2187", "page_type": "职务分组名单页", "structure_group": "shenyang_mobilization_duty_division_paragraphs_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_mobilization_duty_division_paragraphs_v2",
    "leader_region_selector": ".text.artical .TRS_UEDITOR p",
    "name_selector": "人物段落首个冒号前的姓名前缀", "duty_selector": "姓名后排版空白至首个中文冒号",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同段冒号后为职责分工而非主职务；办公信息为其他段落，均须排除",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文段落顺序提取冒号前原始职务并排除职责分工。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in soup.select(".text.artical .TRS_UEDITOR p"):
        raw_text = paragraph.get_text(" ", strip=True)
        matched = re.match(
            r"^((?:[\u3400-\u9fff·][\u2000-\u200b\u3000\xa0]*){2,10})\s+(.+?)：",
            raw_text,
        )
        if matched is None:
            continue
        name = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", matched.group(1))
        evidence = clean_text(matched.group(2))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        if not evidence:
            raise RuntimeError(f"人物段落职务为空：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物段落姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("当前正文未提取到人物段落")
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
