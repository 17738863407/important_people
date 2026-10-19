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
    "rule_id": "3264", "page_type": "人物列表完整页", "structure_group": "wuhan_gardens_forestry_leader_blocks_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page", "parser": "wuhan_gardens_forestry_leader_blocks_v2",
    "leader_region_selector": "div.leader ul.ldjg", "name_selector": "li > ul.list-b > h2.leader", "duty_selector": "li.leader-info中职务后的p.leader-infop",
    "detail_link_selector": "li.leader-info a[href]", "detail_strategy": {"required": True, "mode": "list_link_only", "detail_link_selector": "li.leader-info a[href]", "max_detail_links": 20},
    "risk_flag": "职务和分工为同级h5+p，必须校验标签次序后只取职务p；HTTP头声明ISO-8859-1但正文为UTF-8",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_entry_soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html or "", "html.parser"); fields = soup.select("div.leader ul.ldjg > li > ul.list-b > h2.leader")
    names = [re.sub(r"\s+", "", clean_text(x.get_text(" ", strip=True))) for x in fields]
    if fields and not any(re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) for name in names):
        try: soup = BeautifulSoup((html or "").encode("latin-1").decode("utf-8"), "html.parser")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc: raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
    return soup


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.models import PersonRecord
    soup = parse_entry_soup(html); regions = soup.select("div.leader ul.ldjg")
    if len(regions) != 1: raise RuntimeError(f"领导区域数量异常：{len(regions)}")
    records: list[object] = []; seen_names: set[str] = set(); seen_links: set[str] = set()
    for block in regions[0].select(":scope > li > ul.list-b"):
        name_node = block.select_one(":scope > h2.leader"); info = block.select_one(":scope > li.leader-info")
        labels = [clean_text(x.get_text(" ", strip=True)) for x in info.select(":scope > h5")] if info else []; values = info.select(":scope > p.leader-infop") if info else []; link = info.select_one("a[href]") if info else None
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        if labels != ["职务", "分工"] or len(values) != 2: raise RuntimeError(f"领导职务分工字段结构异常：{name} {labels} {len(values)}")
        evidence = clean_text(values[0].get_text(" ", strip=True)); detail_url = urljoin(final_url, link.get("href", "").strip() if link else ""); split = urlsplit(detail_url)
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence: raise RuntimeError(f"领导姓名或职务异常：{name} {evidence}")
        if split.scheme not in {"http", "https"} or not split.netloc or detail_url == final_url: raise RuntimeError(f"领导详情链接异常：{name} {detail_url}")
        if name in seen_names or detail_url in seen_links: raise RuntimeError(f"领导姓名或详情链接重复：{name} {detail_url}")
        seen_names.add(name); seen_links.add(detail_url)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records: raise RuntimeError("领导区域没有可验证人物记录")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals()); print(f"输出文件：{output_path}")


if __name__ == "__main__": main()
