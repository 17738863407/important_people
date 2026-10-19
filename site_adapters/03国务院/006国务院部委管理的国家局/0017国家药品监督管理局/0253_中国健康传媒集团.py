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
    "rule_id": "0253",
    "page_type": "集团领导人物卡片",
    "structure_group": "health_china_group_leaders",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_health_china_group_leaders_v1",
    "leader_region_selector": ".crbc_zon1.xian",
    "name_selector": ".crbc_zon1.xian .crbcz_right",
    "duty_selector": ".crbc_zon1.xian .crbcz_right",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "集团领导",
        "end_anchor": "",
        "include_selectors": [".crbc_zon1.xian"],
        "exclude_selectors": [".crbc_top", ".crbc_bottom"],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导卡片含长篇履历，且源码残留非当前有效展示的监事会名单；只提取当前集团领导人物卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩HTML节点中的全角空格与其他排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", str(value or "")).strip()


def normalize_name(value: object) -> str:
    """删除姓名字符之间仅用于排版的空白。"""
    return clean_text(value).replace(" ", "")


def append_row(
    rows: list[dict[str, str]],
    name: str,
    duty: str,
    page_rule: dict,
) -> None:
    """校验强结构姓名职务后追加一条结果。"""
    if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) and duty:
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
            }
        )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按当前页面顺序提取集团领导人物卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for card in soup.select(".crbc_zon1.xian .crbcz_right"):
        text_parts = [clean_text(value) for value in card.stripped_strings]
        text_parts = [value for value in text_parts if value]
        if len(text_parts) < 2:
            continue
        append_row(
            rows,
            normalize_name(text_parts[0]),
            text_parts[1],
            page_rule,
        )

    if not rows:
        raise RuntimeError("集团领导页面未提取到有效人物")
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
