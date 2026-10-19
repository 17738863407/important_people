from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2562",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_ecology_leader_list_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_http",
    "parser": "page_nanning_ecology_leader_list_v2",
    "leader_region_selector": "领导介绍栏目人物链接列表",
    "name_selector": "人物链接文本中注入机构名之前",
    "duty_selector": "人物链接完整原文",
    "detail_link_selector": "人物链接href",
    "detail_strategy": {"required": False, "mode": "list_direct_with_detail_url", "max_detail_links": 30},
    "risk_flag": "栏目导航与人物链接混排；必须只接受包含注入机构名且姓名前缀合法的链接文本",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "领导介绍栏目人物链接列表", "name_selector": "链接文本中机构名前", "duty_selector": "同一链接完整原文", "detail_link_selector": "人物链接href"}, "api": {"enabled": False, "reason": "领导列表静态提供姓名、职务和人物详情链接"}},
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", "")).strip()
    if not organization:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        evidence = normalize_layout(anchor.get_text(" ", strip=True))
        split_at = evidence.find(organization)
        if split_at < 2 or len(evidence) > 140:
            continue
        name = evidence[:split_at].replace(" ", "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or name in seen:
            continue
        detail_url = urljoin(final_url, str(anchor.get("href", "")).strip())
        if not detail_url or detail_url == final_url:
            continue
        seen.add(name)
        duty = evidence[split_at:].strip()
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "parser": str(page_rule.get("parser", "")), "selector_summary": "领导介绍人物链接按DOM顺序；以注入机构名切分姓名并保留职务原文"})
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
