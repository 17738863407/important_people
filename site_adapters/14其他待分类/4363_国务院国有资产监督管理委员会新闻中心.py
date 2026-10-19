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
    "rule_id": "4363", "domain": "www.sasac.gov.cn", "page_type": "同段多职务名单页",
    "structure_group": "sasac_center_multirole_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_sasac_center_multirole_v1",
    "leader_region_selector": "dl", "name_selector": "dd p", "duty_selector": "dd p", "detail_link_selector": "",
    "content_scope": {"start_anchor": "中心领导", "end_anchor": "主要职责", "include_selectors": ["dl"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50, "candidate_links": []},
    "risk_flag": "一个段落含多个职务标题，按换行后的职务标签与后续名单配对；无独立人物详情页",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "dl", "name_selector": "dd p", "duty_selector": "dd p", "detail_link_selector": ""}, "api": {"enabled": False, "reason": "中心领导名单由静态HTML直接提供"}, "migration": {"source": "manual_online_verification", "verified_status": "verified_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按同一段落中的换行边界配对职务标题与名单。"""
    soup = BeautifulSoup(html, "html.parser")
    target = next((dl for dl in soup.select("dl") if "中心领导" in clean_text(dl.select_one("dt").get_text(" ", strip=True) if dl.select_one("dt") else "")), None)
    rows: list[dict[str, str]] = []
    if target is None:
        return rows
    current_duty = ""
    for token in [clean_text(part) for part in target.get_text("\n", strip=True).splitlines()]:
        if not token or token == "中心领导":
            continue
        label = re.fullmatch(r"(.{1,30})[：:]", token)
        if label:
            current_duty = re.sub(r"\s+", "", label.group(1))
            continue
        if not current_duty:
            continue
        names_text = re.sub(r"\s+", "", token)
        for name in re.findall(r"[\u4e00-\u9fff·]{2,8}", names_text):
            rows.append({"name": name, "duty": current_duty, "detail_url": "", "evidence": current_duty, "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": "中心领导dl按换行后的职务标签与名单配对"})
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
