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
    "rule_id": "2008",
    "domain": "nxjgsw.nx.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_portrait_links_online_detail_current_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "raw_http",
    "parser": "page_inline_leader_portrait_links_online_detail_current_sentence_v1",
    "detail_link_selector": "a[href*='/ldfg/']",
    "list_name_selector": ".person-name",
    "detail_content_selector": ".view",
    "detail_strategy": {"required": True, "mode": "online_detail_current_sentence"},
    "risk_flag": "入口头像链接文本为空，姓名在同级.person-name；逐详情核名并只取完整现任句，排除工作分工",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """清理HTML排版空白，不改变职务语义。"""
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()
    return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def clean_evidence(value: str) -> str:
    """删除现任句固定前缀及纯句末句号。"""
    return re.sub(r"。$", "", re.sub(r"^现任\s*", "", clean_text(value))).strip()


def extract_current_sentence(html: str, name: str, page_rule: dict[str, object]) -> str:
    """只在当前人物详情正文内提取完整现任句。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("detail_content_selector", "")))
    if region is None:
        return ""
    text = clean_text(region.get_text(" ", strip=True))
    if name not in clean_name(text):
        return ""
    match = re.search(r"现任[^。]*。", text)
    return clean_evidence(match.group(0)) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口人物顺序在线抓取详情并提取现任职务原句。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html or "", "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(str(page_rule.get("detail_link_selector", ""))):
        parent = link.parent
        name_node = parent.select_one(str(page_rule.get("list_name_selector", ""))) if parent else None
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url or source_url, str(link.get("href", "")))
        result = fetch_by_raw_requests(detail_url, timeout=40)
        duty = extract_current_sentence(result.html, name, page_rule)
        if not duty:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": result.final_url or detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=a[href*=/ldfg/] + sibling .person-name；"
                    "detail=.view；pattern=现任[^。]*。；exclude=工作分工"
                ),
            }
        )

    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
