from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4366", "domain": "www.gjxfj.gov.cn", "page_type": "机构负责人字段页",
    "structure_group": "gjxfj_department_principal_v1", "reuse_scope": "same_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_gjxfj_department_principal_v1",
    "leader_region_selector": ".xxgk_znjs1", "name_selector": "p", "duty_selector": "p", "detail_link_selector": "",
    "content_scope": {"start_anchor": "主要负责人：", "end_anchor": "内设机构：", "include_selectors": [".xxgk_znjs1"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50, "candidate_links": []},
    "risk_flag": "仅取正文中“主要负责人”标签后的相邻段落，职务证据为网页字段标签；无人物详情页",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".xxgk_znjs1", "name_selector": "p", "duty_selector": "p", "detail_link_selector": ""}, "api": {"enabled": False, "reason": "机构主要负责人字段由静态HTML直接提供"}, "migration": {"source": "manual_online_verification", "verified_status": "verified_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析“主要负责人”标签后的相邻姓名段落。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".xxgk_znjs1")
    if region is None:
        return []
    label = next((p for p in region.select("p") if clean_text(p.get_text(" ", strip=True)).rstrip("：:") == "主要负责人"), None)
    if label is None:
        return []
    value_node = label.find_next_sibling("p")
    if not isinstance(value_node, Tag):
        return []
    names_text = re.sub(r"\s+", "", clean_text(value_node.get_text(" ", strip=True)))
    return [{"name": name, "duty": "主要负责人", "detail_url": "", "evidence": "主要负责人", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": ".xxgk_znjs1中主要负责人标签的下一p"} for name in re.findall(r"[\u4e00-\u9fff·]{2,8}", names_text)]


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
