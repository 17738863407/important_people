from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1194",
    "domain": "jr.jl.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jilin_finance_current_pointer_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_jilin_finance_current_pointer_v2",
    "detail_strategy": {"required": False, "mode": "inline_with_verified_links"},
    "risk_flag": "入口为当前首位领导详情页；同页侧栏提供完整领导名单",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()
    return re.sub(r"([，、；：])\s+", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按当前领导页侧栏顺序拆分“姓名 职务”并保留动态详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".menulb a.changeStyle[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u3400-\u9fff·]{2,5})\s+(.+)", text)
        if match is None:
            continue
        name = match.group(1)
        duty = clean_text(match.group(2)).strip("，,。 ")
        duty = re.sub(r"[（(]\s*挂职\s*[）)]", "", duty)
        if not duty or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, str(link.get("href", "")))
        if detail_url.rstrip("/") == str(page_rule.get("url", "")).rstrip("/"):
            detail_url = ""
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；current=business-entry；"
                    "row=.menulb a.changeStyle[href]；field=name duty"
                ),
            }
        )

    return records


def main() -> None:
    """运行页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
