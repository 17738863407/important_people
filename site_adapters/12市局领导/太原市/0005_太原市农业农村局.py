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
    "rule_id": "0005",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_agriculture_leader_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_agriculture_leader_paragraphs_v1",
    "leader_region_selector": "#zoom",
    "name_selector": "每段开头至‘太原’职务前缀",
    "duty_selector": "同段‘太原’起始的完整职务文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "二字姓名含多个不间断空格，且职务被拆分到多层span中",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    """删除姓名和职务节点间的纯排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序，以职务的‘太原’前缀确定姓名与职务边界。"""
    del final_url
    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    if regions[0].select_one("a[href]") is not None:
        raise RuntimeError("领导正文出现未审计链接")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in regions[0].select(":scope > p"):
        text = compact_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u3400-\u9fff·]{2,10})(?P<evidence>太原.+)", text)
        if match is None:
            raise RuntimeError(f"人物段落无法确定姓名与职务边界：{text}")
        name = match.group("name")
        evidence = match.group("evidence").rstrip("。")
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "#zoom直属p；合并span并删除排版空白后以‘太原’分隔姓名与职务",
            }
        )

    if not rows:
        raise RuntimeError("领导正文没有可验证的人物段落")
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
