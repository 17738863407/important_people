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
    "rule_id": "4089",
    "page_type": "领导简介页",
    "structure_group": "sitp_leader_strong_intro",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_sitp_leader_strong_intro",
    "leader_region_selector": ".TRS_Editor",
    "risk_flag": "领导标题后的段落含简历和研究方向，依据说明仅保留标题职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从简介段的加粗“职务+姓名”标题中抽取，不读取后续简历字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for node in soup.select(".TRS_Editor p > strong"):
        text = re.sub(r"\s+", "", node.get_text(" ", strip=True))
        split = next(
            (
                (text[:-name_length], text[-name_length:])
                for name_length in (2, 3, 4)
                if re.search(r"(?:所长|书记|主任|院长)$", text[:-name_length])
            ),
            None,
        )
        if split is not None:
            rows.append({"name": split[1], "duty": split[0], "evidence": split[0]})
    return rows


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
