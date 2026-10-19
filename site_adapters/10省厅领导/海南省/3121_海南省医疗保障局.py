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
    "rule_id": "3121",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "parser": "hainan_healthcare_security_leader_cards_v3",
    "leader_region_selector": ".jgjs-lm1-l a[href]",
    "name_selector": "p",
    "duty_selector": "span",
    "detail_link_selector": "当前人物卡片a[href]",
    "locator_strategy": "custom_parse_page",
    "filter_policy": "strong_no_wordlist",
    "confidence": "high",
    "risk_flag": "普通requests会跟随脚本跳至缺少领导卡片的移动页；职务原文方括号必须保留",
}


def _clean_text(value: object) -> str:
    """仅清理HTML排版空白，不改写原文语义和标点。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按省局领导卡片DOM顺序提取姓名、职务和独立详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url or page_rule["url"]
    records: list[PersonRecord] = []
    seen_names: set[str] = set()
    for card in soup.select(page_rule["leader_region_selector"]):
        name_node = card.select_one("p")
        duty_node = card.select_one("span")
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        detail_url = urljoin(source_url, str(card.get("href") or "").strip())
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence=page_rule["confidence"],
                parser=page_rule["parser"],
            )
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
