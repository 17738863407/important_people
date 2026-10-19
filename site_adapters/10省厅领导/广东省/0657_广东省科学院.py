from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0657",
    "page_type": "多人物详情合并页",
    "structure_group": "gdas_current_leader_parenthesized_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "ul#content.comment_list",
    "name_selector": "ul#content.comment_list li a[title][href]",
    "duty_selector": "ul#content.comment_list li a[title][href]",
    "detail_link_selector": "ul#content.comment_list li a[title][href]",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "现任与其他栏目混合，严格限制在现任领导列表并校验姓名（职务）结构",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按现任领导列表顺序解析“姓名（职务）”链接。"""
    from bs4 import BeautifulSoup

    del page_rule
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for anchor in soup.select("ul#content.comment_list li a[title][href]"):
        evidence = _clean_text(anchor.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u4e00-\u9fff]{2,4})（([^）]+)）", evidence)
        if match is None:
            continue
        name = match.group(1)
        duty = _clean_text(match.group(2))
        if not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, anchor.get("href", "")),
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
