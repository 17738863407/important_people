from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1364",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_science_leader_division_article_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_http",
    "parser": "page_nanning_science_leader_division_article_v2",
    "leader_region_selector": ".content",
    "name_selector": "正文短标题段内职务前缀之前",
    "duty_selector": "正文短标题段完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "领导标题段与分工段交替排列；必须只接受含稳定职务前缀的短标题段，排除分工和文件依据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".content",
            "name_selector": "短标题段内职务前缀之前",
            "duty_selector": "同一短标题段完整原文",
        },
        "api": {"enabled": False, "reason": "正文短标题段直接列出姓名和职务"},
    },
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def split_title(text: str) -> tuple[str, str]:
    value = normalize_layout(text)
    if not value or len(value) > 80:
        return "", ""
    matches = [value.find(prefix) for prefix in ("局党组", "党组", "副局长", "局一级", "局二级", "局三级", "局四级")]
    positions = [position for position in matches if position >= 2]
    if not positions:
        return "", ""
    split_at = min(positions)
    name = value[:split_at].replace(" ", "")
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
        return "", ""
    return name, value


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".content")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        name, evidence = split_title(paragraph.get_text(" ", strip=True))
        if not name or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".content短标题段按DOM顺序；以稳定职务前缀切分姓名并保留同一段原文",
            }
        )
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
