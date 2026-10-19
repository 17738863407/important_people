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
    "rule_id": "3712",
    "page_type": "首页领导成员列表",
    "structure_group": "rugby_association_leadership_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_rugby_association_leadership_v1",
    "leader_region_selector": ".leadership",
    "name_selector": "",
    "duty_selector": ".leadership b",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "协会领导成员", "end_anchor": "会员管理系统", "include_selectors": [".leadership"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "首页新闻含其他机构领导姓名，必须严格限定.leadership；同一职务对应顿号分隔多人名单",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_bold_duty_name_lists",
    "locator": {"css": {"container_selector": ".leadership", "duty_selector": ".leadership b"}, "api": {"enabled": False, "reason": "原始HTML中的.leadership直接提供协会领导成员"}, "migration": {"source": "new_verified_online", "verified_status": "verified_current_online"}},
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_names(value: str) -> list[str]:
    names = [clean_text(item).replace(" ", "") for item in re.split(r"[、，,；;]", value)]
    return [name for name in names if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".leadership")
    if container is None:
        return []
    lines = [clean_text(item) for item in container.get_text("\n", strip=True).splitlines() if clean_text(item)]
    rows: list[dict[str, str]] = []
    pending_duty = ""
    for line in lines:
        normalized = line.replace("：", ":", 1)
        if normalized.endswith(":"):
            pending_duty = clean_text(normalized[:-1]).replace(" ", "")
            continue
        if not pending_duty:
            continue
        for name in parse_names(line):
            rows.append({"name": name, "duty": pending_duty, "detail_url": "", "source_text": pending_duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=.leadership；order=duty_group_then_name_list"})
        pending_duty = ""
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
