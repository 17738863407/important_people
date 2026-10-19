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
    """压缩全角空格、换行和连续空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导介绍链接顺序拆分姓名、原始职务和详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".left_news .page_list_3 a[href]"):
        href = str(link.get("href") or "")
        if "/jld/" not in href:
            continue
        text = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,8})\s+(?P<duty>省民营经济发展局.+)$", text)
        if match is None or match.group("name") in seen:
            continue
        name, evidence = match.group("name"), match.group("duty")
        detail_url = urljoin(final_url, href)
        if not detail_url:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "detail_url": detail_url, "evidence": evidence,
                     "confidence": "high", "parser": "page_inline_shanxi_private_economy_links_v2",
                     "selector_summary": "leader=.left_news .page_list_3 a[href*=jld/]；name/duty=title split；detail=href"})
    return rows


PAGE_RULE = {
    "rule_id": "1740", "page_type": "人物表格页", "structure_group": "shanxi_private_economy_leader_links", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_shanxi_private_economy_links_v2",
    "leader_region_selector": ".left_news .page_list_3 a[href*='/jld/']", "name_selector": "link title before first space", "duty_selector": "link title from 省民营经济发展局", "detail_link_selector": ".left_news .page_list_3 a[href*='/jld/']",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".left_news .page_list_3"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "list_link_only", "detail_collector_type": "raw_http", "detail_link_selector": ".left_news .page_list_3 a[href*='/jld/']", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "姓名与职务合并在链接title中，以省民营经济发展局为职务边界", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".left_news .page_list_3 a[href*='/jld/']", "name_selector": "link title before first space", "duty_selector": "link title from 省民营经济发展局", "detail_link_selector": ".left_news .page_list_3 a[href*='/jld/']", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".left_news .page_list_3"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态HTML领导链接已直出姓名、职务和详情页"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
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
