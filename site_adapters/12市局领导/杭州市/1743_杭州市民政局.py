from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1743",
    "page_type": "人物导航页",
    "structure_group": "hangzhou_civil_affairs_leader_navigation_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "hangzhou_civil_affairs_leader_navigation_v1",
    "leader_region_selector": "a.column[href]",
    "name_selector": "党组职务前文本",
    "duty_selector": "党组开头的原始职务文本",
    "detail_link_selector": "a.column[href]",
    "detail_strategy": {"required": False, "mode": "same_anchor_link", "same_host_only": True},
    "risk_flag": "首个人物链接等于规则入口，按契约不作为详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def compact_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def split_person_text(value: str) -> tuple[str, str]:
    match = re.fullmatch(r"(.+?)\s+(党组.+)", clean_text(value))
    if not match:
        return "", ""
    return compact_name(match.group(1)), clean_text(match.group(2))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导导航DOM原序解析姓名、职务与人物页链接。"""
    soup = BeautifulSoup(html, "html.parser")
    entry = urlparse(final_url)
    entry_path = entry.path.rstrip("/")
    records: list[dict[str, str]] = []
    for anchor in soup.select("a.column[href]"):
        name, duty = split_person_text(anchor.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty:
            continue
        candidate_url = urljoin(final_url, anchor.get("href", ""))
        parsed = urlparse(candidate_url)
        detail_url = candidate_url
        if parsed.netloc.lower() != entry.netloc.lower() or parsed.path.rstrip("/") == entry_path:
            detail_url = ""
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "selector_summary": "a.column领导导航DOM原序；党组职务文本边界",
            }
        )
    if not records:
        raise ValueError("未在市民政局领导导航中解析到有效人物")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
