from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0904",
    "page_type": "人物列表完整页",
    "structure_group": "harbin_name_colon_duty_responsibility_paragraphs",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#detailContent",
    "name_selector": "段首姓名及中文冒号",
    "duty_selector": "冒号后首句",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "只解析段首姓名冒号后的首句职务，排除职责与个人简历",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()
    return re.sub(r"\s*([：:，。、；])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.select("#detailContent p")
    rows: list[dict[str, str]] = []
    for paragraph in paragraphs:
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.match(r"^(?P<name>[\u4e00-\u9fff]{2,4})[：:](?P<duty>[^。；]+)[。；]", text)
        if not match:
            continue
        name = match.group("name")
        if name in {"个人简历", "个人简介"}:
            continue
        duty = clean_text(match.group("duty")).rstrip("。；")
        if not duty or re.match(r"^(?:负责|主持|分管|协助|个人简历|个人简介)", duty):
            raise ValueError(f"段首姓名后未取得可靠原始职务：{name}")
        evidence = duty
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": evidence,
                "detail_url": "",
                "selector_summary": "#detailContent段首姓名冒号后的首句",
            }
        )
    if not rows:
        raise ValueError("领导信息正文未发现段首姓名职务段落")
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
