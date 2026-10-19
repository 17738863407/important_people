from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0925",
    "page_type": "人物列表完整页",
    "structure_group": "harbin_name_comma_full_duty_first_sentence",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#detailContent",
    "name_selector": "段首首个逗号前姓名",
    "duty_selector": "逗号后首句完整职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "保留逗号后首句完整机构职务，排除后续主持、负责、分管与协助内容",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for paragraph in soup.select("#detailContent p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,5})[，,](?P<duty>[^。；]+)[。；]", text)
        if not match:
            continue
        duty = clean_text(match.group("duty"))
        if not duty or re.match(r"^(?:主持|负责|分管|协助)", duty):
            raise ValueError(f"人物段落未取得可靠原始职务：{match.group('name')}")
        evidence = re.sub(r"[（(]\s*挂职\s*[）)]", "", duty).strip()
        rows.append(
            {
                "name": match.group("name"),
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "selector_summary": "#detailContent段首姓名逗号后的首句完整职务",
            }
        )
    if not rows:
        raise ValueError("领导信息正文未发现可验证的人物职务段落")
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
