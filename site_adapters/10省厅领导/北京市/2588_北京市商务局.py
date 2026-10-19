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
    "rule_id": "2588",
    "domain": "sw.beijing.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "beijing_commerce_ldjl_blocks_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_beijing_commerce_ldjl_blocks_v1",
    "risk_flag": "姓名可能含单个全角空格；必须以姓名后的连续双空白作为职务边界",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """将网页排版空白压缩为单个半角空格。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def split_leader_text(value: str) -> tuple[str, str]:
    """以连续两个以上排版空白拆分姓名与原始职务。"""
    parts = re.split(r"\s{2,}", str(value or "").strip(), maxsplit=1)
    if len(parts) != 2:
        return "", ""
    name = re.sub(r"\s+", "", parts[0])
    duty = clean_text(parts[1])
    if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None:
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按商务局领导块DOM原始顺序读取姓名与职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(".ldjl_bg > .ldjl"):
        raw_text = item.get_text(" ", strip=True)
        name, duty = split_leader_text(raw_text)
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".ldjl_bg直属ldjl人物块",
            }
        )
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
