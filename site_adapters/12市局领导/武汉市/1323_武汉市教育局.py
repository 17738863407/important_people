from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1323",
    "page_type": "人物列表完整页",
    "structure_group": "wuhan_education_grouped_title_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "wuhan_education_grouped_title_cards_v2",
    "leader_region_selector": "h3.titleLdbox及其后zfldxxFlex",
    "name_selector": "a.zfldxxFlexli[href]",
    "duty_selector": "当前分组h3.titleLdbox",
    "detail_link_selector": "a.zfldxxFlexli[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_link_only",
        "detail_link_selector": "a.zfldxxFlexli[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "原始响应含完整职务分组；HTTP头无charset，且多人可共享同一分组职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性合并分组与卡片文本空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_entry_soup(html: str) -> BeautifulSoup:
    """必要时严格回转HTTP头缺少charset造成的UTF-8乱码。"""
    soup = BeautifulSoup(html or "", "html.parser")
    fields = soup.select("a.zfldxxFlexli[href]")
    names = [re.sub(r"\s+", "", clean_text(field.get_text(" ", strip=True))) for field in fields]
    if fields and not any(re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) for name in names):
        try:
            repaired_html = (html or "").encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
        soup = BeautifulSoup(repaired_html, "html.parser")
    return soup


def find_group_cards(title: Tag) -> list[Tag]:
    """查找当前职务标题之后、下一职务标题之前的人员卡片容器。"""
    sibling = title.find_next_sibling()
    while sibling is not None and "zfldxxFlex" not in (sibling.get("class") or []):
        if sibling.name == "h3" and "titleLdbox" in (sibling.get("class") or []):
            return []
        sibling = sibling.find_next_sibling()
    return sibling.select("a.zfldxxFlexli[href]") if sibling is not None else []


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按职务分组及组内卡片DOM顺序提取姓名、职务和详情链接。"""
    from crawler_core.models import PersonRecord

    soup = parse_entry_soup(html)
    titles = soup.select("h3.titleLdbox")

    records: list[object] = []
    seen_names: set[str] = set()
    seen_links: set[str] = set()
    for title in titles:
        evidence = clean_text(title.get_text(" ", strip=True))
        cards = find_group_cards(title)
        if not evidence or not cards:
            raise RuntimeError(f"领导职务分组标题或卡片为空：{evidence}")
        for card in cards:
            name = re.sub(r"\s+", "", clean_text(card.get_text(" ", strip=True)))
            detail_url = urljoin(final_url, card.get("href", "").strip())
            parts = urlsplit(detail_url)
            if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None:
                raise RuntimeError(f"领导卡片姓名异常：{name}")
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
        raise RuntimeError("领导信息页没有可验证职务分组卡片")
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
