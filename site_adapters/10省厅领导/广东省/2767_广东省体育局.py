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
    "rule_id": "2767",
    "page_type": "人物列表完整页",
    "structure_group": "gd_sports_inline_org_duty_name_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#container",
    "name_selector": "#container p",
    "duty_selector": "#container p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "新入口已核验；正文段落按机构、职务、姓名连续文本排列",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", "", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从“机构+职务+姓名，履历”段落中提取职务和姓名。"""
    from bs4 import BeautifulSoup

    del final_url
    soup = BeautifulSoup(html, "html.parser")
    organization = _clean_text(str(page_rule.get("organization", "")))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for paragraph in soup.select("#container p"):
        first_clause = re.split(r"[，,]", _clean_text(paragraph.get_text(" ", strip=True)), maxsplit=1)[0]
        if not organization or not first_clause.startswith(organization):
            continue
        remainder = first_clause[len(organization) :]
        match = re.fullmatch(r"(.+?(?:书记|局长))([\u4e00-\u9fff]{2,4})", remainder)
        if match is None:
            continue
        duty = match.group(1)
        name = match.group(2)
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": first_clause[: -len(name)],
                "detail_url": "",
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
