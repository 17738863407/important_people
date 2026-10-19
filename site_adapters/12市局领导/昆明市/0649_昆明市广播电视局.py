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
    "rule_id": "0649",
    "page_type": "多人物详情合并页",
    "structure_group": "kunming_broadcast_inline_present_sentence_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_broadcast_inline_present_sentence_v2",
    "leader_region_selector": ".content p",
    "name_selector": ".content p",
    "duty_selector": ".content p",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "max_detail_links": 0,
    },
    "risk_flag": "人物段落混有大量历任经历，只接受该人物段落最后一个完整“现任……”句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_biography(text: str) -> tuple[str, str]:
    biography = clean_text(text)
    name_match = re.match(r"^(?P<name>[\u4e00-\u9fa5]{2,4})，", biography)
    current_sentences = re.findall(r"现任[^。]*。", biography)
    if not name_match or not current_sentences:
        return "", ""
    return name_match.group("name"), clean_text(current_sentences[-1])


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从每个人物简介段提取姓名及最后一个完整现任职务原句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".content") or soup
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in content.select("p"):
        name, evidence = parse_biography(paragraph.get_text(" ", strip=True))
        if not name or not evidence or name in seen:
            continue
        evidence = re.sub(r"^现任\s*", "", evidence).rstrip("。")
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high",
                "parser": page_rule["parser"],
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
