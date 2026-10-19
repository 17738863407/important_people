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
    "rule_id": "0679",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "parser": "beijing_broadcast_leader_cards_v3",
    "leader_region_selector": ".zwxx .nav_zwxxL_con2L a[href], .zwxx .b_0908 a[href]",
    "name_selector": ".nav_zwxxL_con2L a首行, .name_0911",
    "duty_selector": ".nav_zwxxL_con2L a次行, .jop_name",
    "detail_link_selector": "当前人物卡片a[href]",
    "locator_strategy": "custom_parse_page",
    "filter_policy": "strong_no_wordlist",
    "confidence": "high",
    "risk_flag": "首位与其余人物卡片字段顺序相反，分别解析后保持页面顺序",
}


def _clean_text(value: object) -> str:
    """仅清理HTML排版空白，不改写原文语义。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def _normalize_name(value: object) -> str:
    """移除姓名内部仅用于排版的空白。"""
    return re.sub(r"\s+", "", _clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按页面领导介绍模块顺序提取两种强结构人物卡片。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url or page_rule["url"]
    records: list[PersonRecord] = []
    seen_names: set[str] = set()

    candidates: list[tuple[object, str, str]] = []
    main_link = soup.select_one(".zwxx .nav_zwxxL_con2L a[href]")
    if main_link is not None:
        texts = [_clean_text(text) for text in main_link.stripped_strings if _clean_text(text)]
        if len(texts) >= 2:
            candidates.append((main_link, texts[0], texts[1]))
    for link in soup.select(".zwxx .b_0908 a[href]"):
        name_node = link.select_one(".name_0911")
        duty_node = link.select_one(".jop_name")
        candidates.append(
            (
                link,
                name_node.get_text(" ", strip=True) if name_node else "",
                duty_node.get_text(" ", strip=True) if duty_node else "",
            )
        )

    for link, raw_name, raw_duty in candidates:
        name = _normalize_name(raw_name)
        duty = _clean_text(raw_duty)
        detail_url = urljoin(source_url, str(link.get("href") or "").strip())
        if detail_url.rstrip("/") == source_url.rstrip("/"):
            detail_url = ""
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
