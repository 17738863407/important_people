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
    "rule_id": "3129",
    "domain": "ybj.jl.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jilin_medical_security_compound_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_jilin_medical_security_compound_paragraphs_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名、机构和职务位于同一正文段落并含中文排版空格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    """移除同一结构字段中的HTML排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按正文段落顺序拆分姓名与网页原有“机构+职务”字段。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for paragraph in soup.select(".ybj-content3 .TRS_Editor p"):
        text = compact_text(paragraph.get_text(" ", strip=True))
        boundary = text.find(organization)
        if boundary <= 0:
            continue
        name = text[:boundary]
        raw_duty = text[boundary:].strip("，,。 ")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not raw_duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": organization,
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": raw_duty,
                "detail_url": "",
                "evidence": raw_duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；row=.ybj-content3 .TRS_Editor p；"
                    "field=name-before-injected-organization+verbatim-organization-duty"
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
