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
    "rule_id": "3993",
    "page_type": "中心领导列表页",
    "structure_group": "ngcc_leader_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_ngcc_leader_list_v1",
    "leader_region_selector": ".content_right_middle",
    "name_selector": "span.arclist",
    "duty_selector": "span.arclist",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".content_right_middle"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面含通知公告和导航，限定领导之窗内容容器",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验领导列表原始顺序和文本结构",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".content_right_middle", "name_selector": "span.arclist", "duty_selector": "span.arclist", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".content_right_middle"], "exclude_selectors": []}},
        "api": {"enabled": False, "reason": "领导姓名与职务直接呈现在HTML列表项中"},
        "migration": {"verified_status": "verified"},
    },
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导之窗列表顺序提取姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".content_right_middle")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in root.select("span.arclist"):
        text = clean_text(node.get("title") or node.get_text(" ", strip=True))
        match = re.match(r"^([\u4e00-\u9fff]{2,4})\s+(.+)$", text)
        if match is None:
            continue
        name, duty = match.group(1), clean_text(match.group(2))
        duty = duty.removeprefix("国家基础地理信息中心").strip()
        if not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": ".content_right_middle span.arclist标题文本"})
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
