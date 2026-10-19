from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1281",
    "page_type": "人物列表完整页",
    "structure_group": "wuhan_eit_two_field_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "wuhan_eit_two_field_cards_v2",
    "leader_region_selector": ".pb_currchnl父容器中的直属卡片div",
    "name_selector": "卡片a > .h5:first-of-type",
    "duty_selector": "卡片a > .h5:nth-of-type(2)",
    "detail_link_selector": "卡片a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_link_only",
        "detail_link_selector": "卡片a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "原始响应含完整卡片；online缺失目标结构，且HTTP头无charset可能导致UTF-8姓名乱码",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性合并卡片字段排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_entry_soup(html: str) -> BeautifulSoup:
    """必要时严格回转HTTP头缺少charset造成的UTF-8乱码。"""
    soup = BeautifulSoup(html or "", "html.parser")
    fields = soup.select(".pb_currchnl ~ div a[href] .h5:first-of-type")
    names = [re.sub(r"\s+", "", clean_text(field.get_text(" ", strip=True))) for field in fields]
    if fields and not any(re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) for name in names):
        try:
            repaired_html = (html or "").encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
        soup = BeautifulSoup(repaired_html, "html.parser")
    return soup


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按栏目父容器直属卡片DOM顺序提取两个h5字段和详情链接。"""
    from crawler_core.models import PersonRecord

    soup = parse_entry_soup(html)
    anchors = soup.select(".pb_currchnl")
    if len(anchors) != 1 or anchors[0].parent is None:
        raise RuntimeError(f"领导栏目锚点数量异常：{len(anchors)}")
    cards = []
    for container in anchors[0].parent.select(":scope > div"):
        link = container.select_one(":scope > a[href]")
        if link is not None and len(link.select(":scope > .h5")) == 2:
            cards.append(link)

    records: list[object] = []
    seen_names: set[str] = set()
    seen_links: set[str] = set()
    for card in cards:
        fields = card.select(":scope > .h5")
        name = re.sub(r"\s+", "", clean_text(fields[0].get_text(" ", strip=True)))
        evidence = clean_text(fields[1].get_text(" ", strip=True))
        detail_url = urljoin(final_url, card.get("href", "").strip())
        parts = urlsplit(detail_url)
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence:
            raise RuntimeError(f"领导卡片姓名或职务异常：{name} {evidence}")
        if parts.scheme not in {"http", "https"} or not parts.netloc or detail_url == final_url:
            raise RuntimeError(f"领导卡片详情链接异常：{name} {detail_url}")
        if name in seen_names or detail_url in seen_links:
            raise RuntimeError(f"领导卡片姓名或链接重复：{name} {detail_url}")
        seen_names.add(name)
        seen_links.add(detail_url)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导栏目没有两个h5字段的人物卡片")
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
