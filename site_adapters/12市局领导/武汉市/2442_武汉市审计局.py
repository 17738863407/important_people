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
    "rule_id": "2442", "page_type": "职务分组名单页", "structure_group": "wuhan_audit_duty_name_cards_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page", "parser": "wuhan_audit_duty_name_cards_v2",
    "leader_region_selector": ".middle", "name_selector": ".ldjl-card a.card-title冒号后",
    "duty_selector": ".ldjl-card a.card-title冒号前", "detail_link_selector": ".ldjl-card a.card-title[href]",
    "detail_strategy": {"required": True, "mode": "list_link_only", "detail_link_selector": ".ldjl-card a.card-title[href]", "max_detail_links": 20},
    "risk_flag": "天气iframe与领导信息无关；卡片说明为分工，必须只解析card-title职务冒号姓名；HTTP头声明ISO-8859-1但正文为UTF-8",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_entry_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html or "", "html.parser")
    titles = [clean_text(x.get_text(" ", strip=True)) for x in soup.select(".ldjl-card a.card-title[href]")]
    if titles and not any(re.search(r"[：:]\s*[\u3400-\u9fff·]{2,20}$", title) for title in titles):
        try:
            soup = BeautifulSoup((html or "").encode("latin-1").decode("utf-8"), "html.parser")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
    return soup


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.models import PersonRecord

    soup = parse_entry_soup(html)
    cards = soup.select(".ldjl-card")
    if not cards:
        raise RuntimeError("领导信息页没有可验证职务姓名卡片")
    records: list[object] = []
    seen_names: set[str] = set(); seen_links: set[str] = set()
    for card in cards:
        link = card.select_one("a.card-title[href]")
        title = clean_text(link.get_text(" ", strip=True) if link else "")
        parts_text = re.split(r"[：:]", title)
        if len(parts_text) != 2:
            raise RuntimeError(f"职务姓名标题格式异常：{title}")
        evidence = clean_text(parts_text[0]); name = re.sub(r"\s+", "", clean_text(parts_text[1]))
        detail_url = urljoin(final_url, link.get("href", "").strip() if link else ""); parts = urlsplit(detail_url)
        if not evidence or re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None:
            raise RuntimeError(f"领导职务或姓名异常：{title}")
        if parts.scheme not in {"http", "https"} or not parts.netloc or detail_url == final_url:
            raise RuntimeError(f"领导详情链接异常：{name} {detail_url}")
        if name in seen_names or detail_url in seen_links:
            raise RuntimeError(f"领导姓名或详情链接重复：{name} {detail_url}")
        seen_names.add(name); seen_links.add(detail_url)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
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
