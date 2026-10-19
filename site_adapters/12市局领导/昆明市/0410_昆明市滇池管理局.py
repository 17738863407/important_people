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
    "rule_id": "0410",
    "page_type": "多人物详情合并页",
    "structure_group": "kunming_dianchi_current_sentence_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_dianchi_current_sentence_v2",
    "leader_region_selector": ".content .activity p",
    "name_selector": ".content .activity p",
    "duty_selector": ".content .activity p",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "一、领导班子成员分工",
        "end_anchor": "二、重点工作分工",
        "include_selectors": [".content .activity"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "max_detail_links": 0,
    },
    "risk_flag": "页面后半部分另含调研员安排，必须在第二节前停止",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_name(value: str) -> str:
    return re.sub(r"\s+", "", clean_text(value))


def is_name_heading(text: str) -> bool:
    name = clean_name(text)
    if name in {"简历", "工作分工"}:
        return False
    return bool(re.fullmatch(r"[\u4e00-\u9fa5·]{2,4}", name))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在第一节逐个人物块提取完整“现任……”原句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in soup.select(".content .activity p")]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    in_leader_section = False
    index = 0
    while index < len(paragraphs):
        text = paragraphs[index]
        if text.startswith("一、领导班子成员分工"):
            in_leader_section = True
            index += 1
            continue
        if text.startswith("二、重点工作分工"):
            break
        if not in_leader_section or not is_name_heading(text):
            index += 1
            continue

        name = clean_name(text)
        next_index = index + 1
        while next_index < len(paragraphs):
            candidate = paragraphs[next_index]
            if candidate.startswith("二、重点工作分工") or is_name_heading(candidate):
                break
            next_index += 1
        block_text = " ".join(paragraphs[index + 1 : next_index])
        match = re.search(r"现任[^。]*。", block_text)
        if match and name not in seen:
            evidence = re.sub(r"^现任\s*", "", clean_text(match.group(0))).removesuffix("。").strip()
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
        index = max(index + 1, next_index)
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
