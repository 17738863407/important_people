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
    "rule_id": "0838",
    "page_type": "多人物详情合并页",
    "structure_group": "kunming_sasac_present_sentence_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_sasac_present_sentence_v2",
    "leader_region_selector": ".activity p",
    "name_selector": ".activity p",
    "duty_selector": ".activity p",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "max_detail_links": 0,
    },
    "risk_flag": "单篇正文包含多个人物简介，没有独立人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_current_evidence(value: str) -> str:
    """删除现任句固定标签和纯句末句号，保留完整任职语义。"""
    evidence = re.sub(r"^现任\s*", "", clean_text(value))
    return re.sub(r"。$", "", evidence).strip()


def parse_profile(text: str) -> tuple[str, str]:
    profile = clean_text(text)
    match = re.match(r"(?P<name>[\u4e00-\u9fff]{2,4})，.*?(?P<evidence>现任[^。]*。)", profile)
    if not match:
        return "", ""
    return match.group("name"), clean_current_evidence(match.group("evidence"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按简介段DOM顺序提取姓名及完整现任职务原句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(".activity p"):
        name, evidence = parse_profile(paragraph.get_text(" ", strip=True))
        if not name or not evidence or name in seen:
            continue
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
