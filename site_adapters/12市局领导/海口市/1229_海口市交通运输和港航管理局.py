from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1229",
    "page_type": "人物列表完整页",
    "structure_group": "haikou_transport_duty_colon_name_links",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".lby-lm2",
    "name_selector": ".lby-lm2 li a职务冒号后的姓名",
    "duty_selector": ".lby-lm2 li a冒号前的原始职务",
    "detail_link_selector": ".lby-lm2 li a[href]",
    "detail_strategy": {"required": False, "mode": "links_from_listing", "max_detail_links": 50},
    "risk_flag": "限定领导列表内职务冒号姓名结构，排除分页与栏目链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    pattern = re.compile(r"^(?P<duty>[^：:]{2,80})[：:](?P<name>[\u3400-\u9fff·]{2,12})$")
    rows: list[dict[str, str]] = []
    for link in soup.select(".lby-lm2 li a[href]"):
        match = pattern.fullmatch(compact_text(link.get_text(" ", strip=True)))
        href = str(link.get("href") or "").strip()
        if not match or not href:
            continue
        duty = match.group("duty")
        rows.append({"name": match.group("name"), "duty": duty, "evidence": duty,
                     "detail_url": urljoin(final_url, href),
                     "selector_summary": ".lby-lm2领导链接冒号前职务与冒号后姓名"})
    if not rows:
        raise ValueError("领导列表未发现有效的职务冒号姓名详情链接")
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
