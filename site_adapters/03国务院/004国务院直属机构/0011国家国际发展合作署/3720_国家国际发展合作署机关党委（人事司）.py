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
    "rule_id": "3720", "page_type": "机构职能页领导名单", "structure_group": "cidca_party_personnel_leaders_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_cidca_party_personnel_leaders_v1",
    "leader_region_selector": ".contentr .zwnr", "name_selector": ".contentr .zwnr p", "duty_selector": ".contentr .zwnr p", "detail_link_selector": "", "content_scope": {"start_anchor": "机关党委", "end_anchor": "主要职能", "include_selectors": [".contentr .zwnr"], "exclude_selectors": ["script", "style"]}, "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "三个负责人职务标签不同，不能只筛司长；同一人的机关党委与人事司现职须按网页顺序用全角分号分隔", "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_department_role_paragraphs",
    "locator": {"css": {"container_selector": ".contentr .zwnr", "row_selector": "p"}, "api": {"enabled": False, "reason": "原始HTML直接提供机关党委（人事司）负责人职务与姓名"}, "migration": {"source": "new_verified_online", "verified_status": "verified_current_online"}},
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".contentr .zwnr")
    if container is None:
        return []
    rows: list[dict[str, str]] = []
    for paragraph in container.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True)).replace("：", ":", 1)
        if ":" not in text:
            continue
        duty, name = text.split(":", 1)
        duty = clean_text(duty)
        name = clean_text(name).replace(" ", "")
        if duty.startswith("主要职能") or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        evidence = duty.replace("、", "；")
        rows.append({"name": name, "duty": evidence, "detail_url": "", "source_text": evidence, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=.zwnr；order=paragraph_order；clean=multi_duty_delimiter"})
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
