from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0167",
    "page_type": "人物列表完整页",
    "structure_group": "领导信息图文链接卡片",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "CdgdcLeaderLinkTitleParser_v2",
    "leader_region_selector": "ul.img-ul-list li",
    "name_selector": "a.img-ul-tt",
    "duty_selector": "a.img-ul-tt",
    "detail_link_selector": "a.img-ul-tt[href]",
    "detail_strategy": {"required": False, "mode": "list_card_link"},
    "risk_flag": "普通HTTP可能受412防护，需公共在线浏览器链路；只解析领导卡片链接，排除新闻与正文人物",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导信息卡片DOM顺序拆分链接标题中的职务和姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for link in soup.select("ul.img-ul-list li a.img-ul-tt[href]"):
        text = _clean_text(link.get_text(" ", strip=True))
        matched = re.fullmatch(r"(.+?)\s+([\u4e00-\u9fff·]{2,5})", text)
        if not matched:
            continue
        evidence = matched.group(1).strip()
        name = matched.group(2)
        detail_url = urljoin(base_url, link.get("href", ""))
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": PAGE_RULE["parser"],
                "selector_summary": "ul.img-ul-list li a.img-ul-tt；链接标题为职务+姓名；详情链接取当前卡片href；按DOM顺序",
            }
        )
    if not records:
        raise RuntimeError("领导信息图文链接卡片未解析到人物记录")
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
