from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3232", "page_type": "人物列表完整页", "structure_group": "wuhan_emergency_grouped_leaders_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page", "parser": "wuhan_emergency_grouped_leaders_v2",
    "leader_region_selector": "div.lead_text", "name_selector": "li.list-item p.text_name", "duty_selector": ".title-box .text",
    "detail_link_selector": "li.list-item a[href]", "detail_strategy": {"required": True, "mode": "list_link_only", "detail_link_selector": "li.list-item a[href]", "max_detail_links": 20},
    "risk_flag": "职务为人物组标题，必须按分组及组内DOM顺序继承，不添加机构前缀；HTTP头声明ISO-8859-1但正文为UTF-8",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_entry_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html or "", "html.parser"); fields = soup.select("div.lead_text li.list-item p.text_name")
    names = [re.sub(r"\s+", "", clean_text(x.get_text(" ", strip=True))) for x in fields]
    if fields and not any(re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) for name in names):
        try: soup = BeautifulSoup((html or "").encode("latin-1").decode("utf-8"), "html.parser")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc: raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
    return soup


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.models import PersonRecord
    soup = parse_entry_soup(html); groups = soup.select("div.lead_text")
    if not groups: raise RuntimeError("领导信息页没有可验证职务分组")
    records: list[object] = []; seen_names: set[str] = set(); seen_links: set[str] = set()
    for group in groups:
        duty_node = group.select_one(".title-box .text"); evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        items = group.select("li.list-item")
        if not evidence or not items: raise RuntimeError(f"领导职务分组标题或人物为空：{evidence}")
        for item in items:
            name_node = item.select_one("p.text_name"); link = item.select_one("a[href]")
            name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else "")); detail_url = urljoin(final_url, link.get("href", "").strip() if link else ""); split = urlsplit(detail_url)
            if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None: raise RuntimeError(f"领导姓名异常：{name}")
            if split.scheme not in {"http", "https"} or not split.netloc or detail_url == final_url: raise RuntimeError(f"领导详情链接异常：{name} {detail_url}")
            if name in seen_names or detail_url in seen_links: raise RuntimeError(f"领导姓名或详情链接重复：{name} {detail_url}")
            seen_names.add(name); seen_links.add(detail_url)
            records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals()); print(f"输出文件：{output_path}")


if __name__ == "__main__": main()
