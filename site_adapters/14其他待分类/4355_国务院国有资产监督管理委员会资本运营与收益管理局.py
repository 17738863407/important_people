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
    "rule_id": "4355", "domain": "www.sasac.gov.cn", "page_type": "职务标题多人名单页",
    "structure_group": "sasac_department_leaders_v1", "reuse_scope": "same_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_sasac_department_leaders_v1",
    "leader_region_selector": "dl", "name_selector": "dd p", "duty_selector": "dd p",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "厅局领导", "end_anchor": "主要职责", "include_selectors": ["dl"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50, "candidate_links": []},
    "risk_flag": "按厅局领导区域内职务标题与多人名单解析，无独立人物详情页",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "dl", "name_selector": "dd p", "duty_selector": "dd p", "detail_link_selector": ""}, "api": {"enabled": False, "reason": "厅局领导名单由静态HTML直接提供"}, "migration": {"source": "manual_online_verification", "verified_status": "verified_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析“职务标题：多人名单”结构。"""
    soup = BeautifulSoup(html, "html.parser")
    target = next((dl for dl in soup.select("dl") if "厅局领导" in clean_text(dl.select_one("dt").get_text(" ", strip=True) if dl.select_one("dt") else "")), None)
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    if target is None:
        return rows
    for paragraph in target.select("dd p"):
        match = re.match(r"^([^：:]{1,30})[：:]\s*(.+)$", clean_text(paragraph.get_text(" ", strip=True)))
        if not match:
            continue
        duty = re.sub(r"\s+", "", clean_text(match.group(1)))
        for name in re.findall(r"[\u4e00-\u9fff·]{2,8}", match.group(2)):
            if (name, duty) in seen:
                continue
            seen.add((name, duty))
            rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": "厅局领导dl中的dd p按职务：姓名解析"})
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
