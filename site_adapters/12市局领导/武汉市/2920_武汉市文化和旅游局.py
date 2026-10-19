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
    "rule_id": "2920", "page_type": "人物列表完整页", "structure_group": "wuhan_culture_tourism_leader_cards_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page", "parser": "wuhan_culture_tourism_leader_cards_v2",
    "leader_region_selector": "ul.list-p", "name_selector": "li a[href] h4首文本行", "duty_selector": "li a[href] h4后续文本行",
    "detail_link_selector": "ul.list-p li a[href]", "detail_strategy": {"required": True, "mode": "list_link_only", "detail_link_selector": "ul.list-p li a[href]", "max_detail_links": 20},
    "risk_flag": "卡片href为HTTP绝对详情链接且在线可访问；仅取h4姓名和职务，不拼接姓名为证据；HTTP头声明ISO-8859-1但正文为UTF-8",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_entry_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html or "", "html.parser"); headings = soup.select("ul.list-p li a[href] h4")
    names = [re.sub(r"\s+", "", clean_text(next(iter(h.stripped_strings), ""))) for h in headings]
    if headings and not any(re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) for name in names):
        try: soup = BeautifulSoup((html or "").encode("latin-1").decode("utf-8"), "html.parser")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc: raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
    return soup


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.models import PersonRecord
    soup = parse_entry_soup(html); regions = soup.select("ul.list-p")
    if len(regions) != 1: raise RuntimeError(f"领导列表区域数量异常：{len(regions)}")
    records: list[object] = []; seen_names: set[str] = set(); seen_links: set[str] = set()
    for link in regions[0].select("li a[href]"):
        heading = link.find("h4"); parts = [clean_text(x) for x in heading.stripped_strings] if heading else []
        if len(parts) < 2: raise RuntimeError(f"领导卡片姓名职务行数异常：{parts}")
        name = re.sub(r"\s+", "", parts[0]); evidence = clean_text("".join(parts[1:])); detail_url = urljoin(final_url, link.get("href", "").strip()); split = urlsplit(detail_url)
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence: raise RuntimeError(f"领导姓名或职务异常：{name} {evidence}")
        if split.scheme not in {"http", "https"} or not split.netloc or detail_url == final_url: raise RuntimeError(f"领导详情链接异常：{name} {detail_url}")
        if name in seen_names or detail_url in seen_links: raise RuntimeError(f"领导姓名或详情链接重复：{name} {detail_url}")
        seen_names.add(name); seen_links.add(detail_url)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records: raise RuntimeError("领导列表没有可验证人物卡片")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals()); print(f"输出文件：{output_path}")


if __name__ == "__main__": main()
