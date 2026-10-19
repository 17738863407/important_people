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
    "rule_id": "2901",
    "domain": "wjw.nmg.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "leader_profile_cards_title_fields_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_inline_leader_profile_cards_title_fields_v1",
    "leader_region_selector": ".p_eldbk",
    "title_selector": ".p_eldnr1",
    "name_selector": ".p_eldnr1 .p18",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "每卡后续职责与简介不属于主职务；只读取标题节点的姓名span与直属职务文本",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩页面字段中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按人物卡片DOM顺序提取标题区姓名与原始职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    card_selector = str(page_rule.get("leader_region_selector", ""))
    title_selector = str(page_rule.get("title_selector", ""))
    name_selector = str(page_rule.get("name_selector", ""))

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select(card_selector):
        title = card.select_one(title_selector)
        name_node = card.select_one(name_selector)
        if title is None or name_node is None:
            continue

        name = clean_name(name_node.get_text(" ", strip=True))
        duty = clean_text(" ".join(str(node) for node in title.find_all(string=True, recursive=False)))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；card=.p_eldbk；name=.p_eldnr1 .p18；"
                    "duty=.p_eldnr1直属文本；exclude=职责+简介"
                ),
            }
        )

    return records


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
