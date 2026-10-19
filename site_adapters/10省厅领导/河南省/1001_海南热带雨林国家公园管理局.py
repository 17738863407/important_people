from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1001",
    "page_type": "人物卡片列表页",
    "structure_group": "领导介绍卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "page_inline_hainan_rainforest_leader_cards_v2",
    "leader_region_selector": "#cona_TBABa_3 .ldy-x-ys3-ty-li > a[href]",
    "name_selector": "p",
    "duty_selector": "span",
    "detail_link_selector": "a[href]",
    "risk_flag": "同页包含内设机构等标签，仅解析领导介绍面板中的人物卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """仅清理网页排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def repair_utf8_mojibake(html: str) -> str:
    """仅在中文字符数明确增加时修复被误按Latin-1解码的UTF-8页面。"""
    try:
        candidate = html.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return html
    original_cjk_count = sum("\u4e00" <= char <= "\u9fff" for char in html)
    candidate_cjk_count = sum("\u4e00" <= char <= "\u9fff" for char in candidate)
    return candidate if candidate_cjk_count > original_cjk_count else html


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导介绍面板中的人物卡片顺序解析姓名、职务和详情页。"""
    soup = BeautifulSoup(repair_utf8_mojibake(html), "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select(str(page_rule["leader_region_selector"])):
        name_node = card.select_one(str(page_rule["name_selector"]))
        duty_node = card.select_one(str(page_rule["duty_selector"]))
        name = "".join(clean_text(name_node.get_text(" ", strip=True) if name_node else "").split())
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(card.get("href") or "")),
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#cona_TBABa_3领导介绍面板 > 人物卡片a > p姓名 + span职务",
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
