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
    "rule_id": "0368",
    "page_type": "多人物详情合并页",
    "structure_group": "kunming_profile_sequence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_profile_sequence_v1",
    "leader_region_selector": ".content p",
    "name_selector": ".content p",
    "duty_selector": ".content p",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "max_detail_links": 0,
    },
    "risk_flag": "普通HTTP可能触发网站安全防护；人物标题后紧邻简历段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return re.sub(r"\s*([、，,；;：:])\s*", r"\1", text)


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def parse_name_from_resume(value: str) -> str:
    match = re.match(r"简历[:：]\s*(?P<name>[\u4e00-\u9fa5·\s]{2,12})[，,]", value or "")
    return compact(match.group("name")) if match else ""


def title_to_duty(title: str, name: str) -> str:
    title_compact = compact(title)
    if not title_compact.endswith(name):
        return ""
    return clean_text(title_compact[: -len(name)]).strip("，、；;")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """用相邻简历段确认姓名，以前一标题段原文作为职务证据。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in soup.select(".content p")]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index in range(1, len(paragraphs)):
        resume = paragraphs[index]
        if not resume.startswith("简历"):
            continue
        title = paragraphs[index - 1]
        name = parse_name_from_resume(resume)
        duty = title_to_duty(title, name)
        key = (name, duty)
        if not name or not duty or key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
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
