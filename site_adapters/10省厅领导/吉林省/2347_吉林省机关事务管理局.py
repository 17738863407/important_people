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
    "rule_id": "2347",
    "domain": "sgj.jl.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jilin_agency_affairs_inline_leaders_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_jilin_agency_affairs_inline_leaders_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "增强requests误跳无障碍地址；职务后同段为职责，按首个句号截断",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导简介顺序提取首句职务，并排除后续职责分工。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select("ul.syw_jgzn_text > li"):
        name_node = item.select_one("h1")
        duty_node = item.select_one("p")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True) if name_node else "")
        duty_and_responsibility = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        duty = clean_text(duty_and_responsibility.split("。", 1)[0])
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
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
                    "strategy=custom_parse_page；row=ul.syw_jgzn_text > li；"
                    "name=h1；duty=p first-sentence；detail=none"
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
