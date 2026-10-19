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


def clean_text(value: str) -> str:
    """压缩HTML文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """仅解析中粮集团管理团队中的“领导班子”分组。"""
    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    selector_summary = (
        "strategy=custom_parse_page；"
        "leader=ul.team-box > li.typeart0 .team-list；"
        "name=h1；duty=p；detail=none"
    )

    for card in soup.select("ul.team-box > li.typeart0 .team-list"):
        name_node = card.select_one("h1")
        duty_node = card.select_one("p")
        if name_node is None or duty_node is None:
            continue

        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue

        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_cofco_leadership_team_v2",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0261",
    "domain": "www.cofco.com",
    "page_type": "人物列表完整页",
    "structure_group": "cofco_management_typeart0",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_cofco_leadership_team_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "online会误跟随页面搜索脚本；使用raw_http保留原始管理团队HTML，并限定li.typeart0排除董事会",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "enabled": False,
            "reason": "官网静态HTML直接包含领导班子姓名和职务",
        },
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "online_verified_20260806",
            "behavior_changed": True,
        },
    },
}


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
