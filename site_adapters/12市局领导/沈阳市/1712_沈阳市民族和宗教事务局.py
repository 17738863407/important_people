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
    "rule_id": "1712", "page_type": "人物列表完整页", "structure_group": "shenyang_ethnic_religious_details_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_ethnic_religious_details_v2",
    "leader_region_selector": "ul.xxgk_rul li a[href]", "name_selector": "列表链接文本",
    "duty_selector": "详情.neik.artical .view中姓名独立p之后首个非空p",
    "detail_link_selector": "ul.xxgk_rul li a[href]",
    "detail_strategy": {"required": True, "mode": "limited_inline_detail", "max_detail_links": 50},
    "risk_flag": "职务必须在线逐详情解析；姓名后的简历和分管工作节点不得混入",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def extract_detail_duty(html: str, name: str) -> str:
    """从详情正文姓名独立节点之后读取首个非空职务节点。"""
    soup = BeautifulSoup(html or "", "html.parser")
    nodes = soup.select(".neik.artical .view p")
    name_indexes = [index for index, node in enumerate(nodes) if clean_text(node.get_text(" ", strip=True)) == name]
    if len(name_indexes) != 1:
        raise RuntimeError(f"详情姓名节点命中数量异常：{name}={len(name_indexes)}")
    for node in nodes[name_indexes[0] + 1:]:
        evidence = clean_text(node.get_text(" ", strip=True))
        if evidence:
            return evidence
    raise RuntimeError(f"详情姓名之后未找到职务节点：{name}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按列表顺序在线抓取详情页原始职务。"""
    from crawler_core.fetcher import fetch_online_html_with_fallback
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    source_url = final_url or page_rule["url"]
    records: list[object] = []
    seen_names: set[str] = set()
    for link in soup.select("ul.xxgk_rul li a[href]"):
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        href = clean_text(link.get("href", ""))
        detail_url = urljoin(source_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not detail_url:
            raise RuntimeError("部门领导列表姓名或详情链接异常")
        if name in seen_names:
            raise RuntimeError(f"部门领导姓名重复：{name}")
        detail_html = fetch_online_html_with_fallback(detail_url).html
        evidence = extract_detail_duty(detail_html, name)
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("当前页面未提取到部门领导")
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
