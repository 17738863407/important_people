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
    "rule_id": "1473",
    "page_type": "多人物详情合并页",
    "structure_group": "gx_forestry_combined_h5_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#LDcontent",
    "name_selector": "#LDcontent .bt-box1 h5 span",
    "duty_selector": "#LDcontent .bt-box1 h5",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一合并页直接承载6人姓名职务，无独立人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按合并页h5顺序提取span姓名及标题尾部原始职务。"""
    from bs4 import BeautifulSoup

    del final_url, page_rule
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for heading in soup.select("#LDcontent .bt-box1 h5"):
        name_node = heading.select_one("span")
        if name_node is None:
            continue
        raw_name = _clean_text(name_node.get_text(" ", strip=True))
        name = re.sub(r"\s+", "", raw_name)
        full_text = _clean_text(heading.get_text(" ", strip=True))
        duty = _clean_text(full_text.removeprefix(raw_name)).strip("：:，,。")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty or name in seen:
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
