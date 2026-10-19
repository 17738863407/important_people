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
    "rule_id": "0845",
    "domain": "gzw.nx.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_assignment_rows_name_duty_responsibility_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_inline_leader_assignment_rows_name_duty_responsibility_v1",
    "leader_row_selector": "div.ldfg",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "每行含姓名、职务和负责/协助/主持分工；依据只保留分工动词前的原始职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


DUTY_START_KEYWORDS = ("党委副书记", "党委书记", "党委委员", "副主任", "主任")


def clean_text(value: object) -> str:
    """压缩分工行的全角及普通排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def split_leader_row(value: object) -> tuple[str, str]:
    """从“姓名 职务 负责/协助/主持……”行中拆分姓名和职务。"""
    text = clean_text(value)
    positions = [text.find(keyword) for keyword in DUTY_START_KEYWORDS if text.find(keyword) > 0]
    if not positions:
        return "", ""
    duty_start = min(positions)
    name = re.sub(r"\s+", "", text[:duty_start])
    duty_and_work = text[duty_start:]
    duty = clean_text(re.split(r"\s+(?:负责|协助|主持)", duty_and_work, maxsplit=1)[0])
    if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导分工行DOM顺序提取姓名和分工前的职务字段。"""
    soup = BeautifulSoup(html or "", "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in soup.select(str(page_rule.get("leader_row_selector", ""))):
        name, duty = split_leader_row(row.get_text(" ", strip=True))
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；row=div.ldfg；"
                    "name=职务关键词前文本；duty=负责/协助/主持前文本；exclude=分工"
                ),
            }
        )

    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
