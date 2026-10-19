from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1803",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_ethnic_religious_duty_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_ethnic_religious_duty_groups_v1",
    "leader_region_selector": ".zfxxgk_ld",
    "name_selector": ".zfxxgk_ld .ldcon a[href]",
    "duty_selector": ".zfxxgk_ld .ldtit",
    "detail_link_selector": ".zfxxgk_ld .ldcon a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_list_links",
        "detail_link_selector": ".zfxxgk_ld .ldcon a[href]",
        "max_detail_links": 10,
    },
    "risk_flag": "duty_heading_applies_to_one_or_multiple_ordered_name_links",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "group_selector": ".zfxxgk_ld",
            "duty_selector": ".ldtit",
            "name_link_selector": ".ldcon a[href]",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线HTML直接包含2个职务分组、3个姓名链接和对应独立人物页",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按职务分组及组内姓名链接顺序提取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for group in soup.select(".zfxxgk_ld"):
        duty_node = group.select_one(".ldtit")
        if duty_node is None:
            continue
        duty = re.sub(r"\s+", "", normalize_space(duty_node.get_text(" ", strip=True)))
        if not duty:
            continue
        for link in group.select(".ldcon a[href]"):
            name = re.sub(r"\s+", "", normalize_space(link.get_text(" ", strip=True)))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen_names:
                continue
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(final_url, str(link.get("href", "")).strip()),
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": ".zfxxgk_ld职务分组；.ldtit原始职务；.ldcon姓名链接顺序及动态独立人物页",
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
