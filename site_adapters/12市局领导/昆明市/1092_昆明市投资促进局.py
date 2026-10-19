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
    "rule_id": "1092",
    "page_type": "职务分组名单页",
    "structure_group": "kunming_invest_duty_colon_name_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_invest_duty_colon_name_v2",
    "leader_region_selector": ".activity p",
    "name_selector": ".activity p",
    "duty_selector": ".activity p",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "max_detail_links": 0,
    },
    "risk_flag": "正文后部另有分工协作关系，必须只接受完整职务冒号姓名段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_duty_name(text: str) -> tuple[str, str]:
    line = clean_text(text)
    match = re.fullmatch(r"(?P<duty>.+?)[：:](?P<name>[\u4e00-\u9fff·]{2,4})", line)
    if not match:
        return "", ""
    duty = clean_text(match.group("duty"))
    if not any(token in duty for token in ("书记", "局长", "副局长", "调研员")):
        return "", ""
    return match.group("name"), duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按职务姓名段在正文中的原始DOM顺序提取人物。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(".activity p"):
        evidence = clean_text(paragraph.get_text(" ", strip=True))
        name, duty = parse_duty_name(evidence)
        if not name or not duty or name in seen:
            continue
        seen.add(name)
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
