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
    "rule_id": "0006",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_justice_leader_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_justice_leader_paragraphs_v1",
    "leader_region_selector": "#zoom",
    "name_selector": ":scope > p strong",
    "duty_selector": "姓名后的首个冒号之前",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名含全角排版空格；冒号后为分工职责，不得混入职务证据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理正文中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def clean_name(value: str) -> str:
    """删除姓名中的排版空格，不改变姓名字符。"""
    return re.sub(r"\s+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序提取加粗姓名及冒号前的明确职务。"""
    del final_url
    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in regions[0].select(":scope > p"):
        name_node = paragraph.select_one("strong")
        if name_node is None:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            raise RuntimeError(f"人物姓名异常：{name}")

        paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
        remaining = clean_text(paragraph_text.replace(clean_text(name_node.get_text(" ", strip=True)), "", 1))
        evidence = clean_text(re.split(r"[：:]", remaining, maxsplit=1)[0])
        if not evidence or evidence == remaining:
            raise RuntimeError(f"人物段落缺少可验证的职务与职责分隔：{name}")
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
                "selector_summary": "#zoom直属p中的strong姓名；同段姓名后首个冒号前为职务",
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
