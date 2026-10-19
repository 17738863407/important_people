from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0965",
    "page_type": "多人物详情合并页",
    "structure_group": "postal_content_body_current_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".zfxx-box .content-body",
    "name_selector": ".content-body > p人物句首姓名",
    "duty_selector": ".content-body > p同句完整现任原文",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "机构领导",
        "end_anchor": "附件",
        "include_selectors": [".zfxx-box .content-body > p"],
        "exclude_selectors": [".zfxx-box .content-body > p.rq"],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "正文另含隐藏发布日期与附件区，只解析content-body直接子段落中的姓名现任首句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()
    return re.sub(r"\s+。", "。", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    pattern = re.compile(
        r"^(?P<name>[\u3400-\u9fff·]{2,12})[，,]"
        r"(?P<evidence>现任(?P<duty>[^。]+)。)"
    )
    for paragraph in soup.select(".zfxx-box .content-body > p:not(.rq)"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = pattern.match(text)
        if not match:
            continue
        rows.append(
            {
                "name": match.group("name"),
                "duty": match.group("duty"),
                "evidence": match.group("duty"),
                "detail_url": "",
                "selector_summary": ".zfxx-box .content-body直接人物段落现任首句",
            }
        )
    if not rows:
        raise ValueError("机构领导正文未发现句首姓名与完整现任原句")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
