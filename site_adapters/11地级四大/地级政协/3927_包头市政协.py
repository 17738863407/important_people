from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3927",
    "page_type": "无链接人物图文卡片",
    "structure_group": "baotou_cppcc_text_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_baotou_cppcc_cards_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".zxld-lists-bottom",
    "name_selector": ".zxld-lists-bottom-name文本末尾姓名",
    "duty_selector": ".zxld-lists-bottom-name姓名前职务",
    "detail_link_selector": "none_no_anchor",
    "risk_flag": "卡片无人物链接，图片也没有可验证详情目标",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按图文卡片顺序拆分姓名前的完整职务。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(".zxld-lists-bottom")
    if region is None:
        raise RuntimeError("未定位到政协领导图文卡片区域")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for card in region.select(":scope > .zxld-lists-bottom-div"):
        field = card.select_one(".zxld-lists-bottom-name")
        text_value = clean_text(field.get_text(" ", strip=True) if field else "")
        field_match = re.fullmatch(r"(.+?)\s+([\u3400-\u9fff·]{2,20})", text_value)
        if field_match is None:
            continue
        evidence = clean_text(field_match.group(1))
        name = field_match.group(2)
        if name in seen_names or not evidence:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": ".zxld-lists-bottom直属卡片name字段",
            }
        )

    if not rows:
        raise RuntimeError("政协领导图文卡片未提取到有效人物")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
