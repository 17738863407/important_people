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
    "rule_id": "0929",
    "page_type": "人物表格页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "profile_blocks",
    "parser": "hebei_drc_name_duty_paragraph_pairs_v3",
    "leader_region_selector": "table.bordertab td.rgt_tab .TRS_Editor",
    "name_selector": "姓名独占p",
    "duty_selector": "姓名后首个非空p",
    "detail_link_selector": "",
    "locator_strategy": "custom_parse_page",
    "filter_policy": "strong_no_wordlist",
    "confidence": "high",
    "risk_flag": "普通requests会错误跟随脚本至外部登录页；按姓名独占段落与下一非空段落动态配对",
}


def _clean_text(value: object) -> str:
    """仅清理HTML排版空白，不改写原文语义和标点。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文段落顺序动态配对姓名独占段与其后的完整职务段。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(page_rule["leader_region_selector"])
    if scope is None:
        return []

    paragraphs = [_clean_text(node.get_text("", strip=True)) for node in scope.select("p")]
    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for index, text in enumerate(paragraphs):
        name = re.sub(r"\s+", "", text)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or name in seen_names:
            continue
        duty = next((item for item in paragraphs[index + 1 :] if item), "")
        if not duty or re.fullmatch(r"[\u3400-\u9fff·]{2,8}", re.sub(r"\s+", "", duty)):
            continue
        duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty).rstrip("。")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
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
