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
    "rule_id": "0162",
    "page_type": "人物卡片页",
    "structure_group": "职务姓名组合卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "ChengduCppccLeaderCardParser_v2",
    "leader_region_selector": ".container.w.leader ul.list-member4 li",
    "name_selector": "p.l-name",
    "duty_selector": "p.l-name",
    "detail_link_selector": "a.image[href]",
    "risk_flag": "普通HTTP请求可能返回403，需由online采集器轮换请求画像",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一HTML排版空白。"""
    return " ".join(str(value or "").replace("\xa0", " ").replace("\u3000", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按卡片DOM顺序拆分“职务：姓名”强结构字段。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for card in soup.select(rule["leader_region_selector"]):
        label_node = card.select_one(rule["name_selector"])
        raw_evidence = _clean_text(label_node.get_text(" ", strip=True) if label_node else "")
        separator = "：" if "：" in raw_evidence else ":" if ":" in raw_evidence else ""
        if not separator:
            continue
        duty, name = [_clean_text(part) for part in raw_evidence.split(separator, 1)]
        name = "".join(name.split())
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or (name, duty) in seen:
            continue
        seen.add((name, duty))
        link = card.select_one(rule["detail_link_selector"])
        href = (link.get("href") or "").strip() if link else ""
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, href) if href else "",
                "parser": rule["parser"],
                "selector_summary": "领导卡片p.l-name组合字段；a.image人物详情",
            }
        )
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
