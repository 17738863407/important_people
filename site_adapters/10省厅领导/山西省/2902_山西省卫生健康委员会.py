from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def split_name_duty(raw_text: str) -> tuple[str, str]:
    """利用姓名与职务间至少两个空白字符拆分字段。"""
    normalized = str(raw_text or "").replace("\u3000", " ").replace("\u00a0", " ")
    match = re.match(r"^\s*(?P<name>[\u4e00-\u9fff· ]{2,12}?)\s{2,}(?P<duty>.+?)\s*$", normalized, re.S)
    if match is None:
        return "", ""
    return re.sub(r"\s+", "", match.group("name")), clean_text(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导分工列表顺序提取姓名、职务和详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = next((node for node in soup.select(".demo-right") if node.select_one("li a[href]")), None)
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in region.select("li a[href]"):
        name, evidence = split_name_duty(link.get_text("", strip=True))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence or not detail_url or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "detail_url": detail_url, "evidence": evidence,
                     "confidence": "high", "parser": "page_inline_shanxi_health_leader_list_v2",
                     "selector_summary": "region=.demo-right containing li a；name/duty=link text split by double-space；detail=href"})
    return rows


PAGE_RULE = {
    "rule_id": "2902", "page_type": "人物列表完整页", "structure_group": "shanxi_health_leader_list", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_shanxi_health_leader_list_v2",
    "leader_region_selector": ".demo-right li a[href]", "name_selector": "link text before double-space", "duty_selector": "link text after double-space", "detail_link_selector": ".demo-right li a[href]",
    "content_scope": {"start_anchor": "领导分工", "end_anchor": "", "include_selectors": [".demo-right"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "list_link_only", "detail_collector_type": "raw_http", "detail_link_selector": ".demo-right li a[href]", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "姓名内部使用单个全角空格，姓名职务间使用两个不换行空格和换行，以至少两个空白确定字段边界", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".demo-right li a[href]", "name_selector": "link text before double-space", "duty_selector": "link text after double-space", "detail_link_selector": ".demo-right li a[href]", "content_scope": {"start_anchor": "领导分工", "end_anchor": "", "include_selectors": [".demo-right"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态HTML领导分工列表已直出姓名、职务和详情页"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
