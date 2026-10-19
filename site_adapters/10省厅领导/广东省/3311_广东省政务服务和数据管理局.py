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
    "rule_id": "3311",
    "page_type": "人物列表完整页",
    "structure_group": "gd_data_service_colon_paragraph_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".zw",
    "name_selector": ".zw p",
    "duty_selector": ".zw p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名职务段与分工段交替；仅接受姓名冒号职务段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序解析“姓名：原始职务”记录。"""
    from bs4 import BeautifulSoup

    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for node in soup.select(".zw p"):
        evidence = _clean_text(node.get_text("", strip=True))
        match = re.fullmatch(r"([\u4e00-\u9fff]{2,4})\s*[：:]\s*(.+)", evidence)
        if match is None:
            continue
        name = match.group(1)
        duty = _clean_text(match.group(2)).rstrip("。；;")
        if not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
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
