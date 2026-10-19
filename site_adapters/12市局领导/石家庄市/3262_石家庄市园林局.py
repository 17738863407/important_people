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
    "rule_id": "3262", "page_type": "人物列表完整页", "structure_group": "sjz_garden_strong_parentheses_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_garden_strong_parentheses_v2",
    "leader_region_selector": "#conN strong", "name_selector": "strong左括号前",
    "duty_selector": "strong中文括号内完整原文", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "strong父div后续为主持、分管或协助职责；禁止给括号内职务补写机构前缀",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    """移除姓名和括号职务中的排版空白，不增加或删改机构文字。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按strong中的姓名和中文括号职务强结构解析。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    title_nodes = regions[0].select("strong")
    if not title_nodes:
        raise RuntimeError("领导正文没有strong人物标题")
    pattern = re.compile(r"^(?P<name>[\u3400-\u9fff·]{2,10})（(?P<evidence>.+)）$")

    records: list[object] = []
    seen_names: set[str] = set()
    for title_node in title_nodes:
        title = compact_text(title_node.get_text(" ", strip=True))
        match = pattern.fullmatch(title)
        if match is None:
            raise RuntimeError(f"strong人物标题结构异常：{title}")
        name = match.group("name")
        evidence = match.group("evidence")
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物职务为空或姓名重复：{name}")
        parent = title_node.parent
        if parent is None or parent.select_one("a[href]") is not None:
            raise RuntimeError(f"人物标题父节点缺失或出现未审计链接：{name}")

        seen_names.add(name)
        records.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"],
        ))
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
