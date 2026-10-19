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
    "rule_id": "0528", "page_type": "多人物详情合并页", "structure_group": "farmchina_current_leader_groups_v2", "reuse_scope": "single_page", "load_mode": "动态DOM渲染", "fetch_mode": "online", "force_browser": True, "extract_mode": "list_direct", "collector": "browser_dom", "parser": "page_inline_farmchina_current_leader_groups_v2",
    "leader_region_selector": "#catg_main_content > div:first-of-type", "name_selector": "colon suffix split dunhao", "duty_selector": "colon prefix", "detail_link_selector": "",
    "content_scope": {"start_anchor": "现任领导", "end_anchor": "历任领导", "include_selectors": ["#catg_main_content > div:first-of-type"], "exclude_selectors": ["#catg_main_left", ".navbar-default", "footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "browser_dom", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "普通HTTP可能返回403访问过于频繁，需公共在线浏览器链路取得现任领导分组", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_current_group_block",
    "locator": {"css": {"leader_region_selector": "#catg_main_content > div:first-of-type", "row_pattern": "主任或副主任冒号姓名列表"}, "api": {"enabled": False, "reason": "未发现可复现接口"}, "migration": {"source": "legacy_business_source_and_offline_dependency_removed", "verified_status": "verified_current_online_browser", "behavior_changed": True}},
}


def compact(value: str) -> str:
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()
    return re.sub(r"\s*([、，,；;：:])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    block = soup.select_one(page_rule["leader_region_selector"])
    if block is None:
        return []
    text = compact(block.get_text(" ", strip=True))
    rows: list[dict[str, str]] = []
    for match in re.finditer(r"(?P<duty>主任|副主任)[:：](?P<names>[^:：]+?)(?=(?:主任|副主任)[:：]|$)", text):
        duty = match.group("duty")
        for raw_name in re.split(r"[、，,]", match.group("names")):
            name = re.sub(r"\s+", "", raw_name)
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name):
                rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": match.group(0), "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=current_leader_group；order=group_then_name"})
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
