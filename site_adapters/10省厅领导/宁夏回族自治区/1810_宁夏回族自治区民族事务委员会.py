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
    "rule_id": "1810",
    "domain": "mzzj.nx.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_links_title_name_duty_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_inline_leader_links_title_name_duty_v1",
    "leader_link_selector": "a[title*='自治区民委'][href]",
    "detail_strategy": {"required": False, "mode": "card_link"},
    "risk_flag": "站点HTTPS证书过期，使用公共raw_http增强采集器SSL降级；title内姓名可能含排版空格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩title字段中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def split_title(value: object) -> tuple[str, str]:
    """从“姓名 自治区民委职务”title中拆分姓名和职务。"""
    text = clean_text(value)
    match = re.fullmatch(r"([\u3400-\u9fff](?:\s*[\u3400-\u9fff·]){1,7})\s+(自治区民委.+)", text)
    if match is None:
        return "", ""
    name = re.sub(r"\s+", "", match.group(1))
    return name, clean_text(match.group(2))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导简介链接DOM顺序提取title强字段和详情链接。"""
    soup = BeautifulSoup(html or "", "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(str(page_rule.get("leader_link_selector", ""))):
        name, duty = split_title(link.get("title") or link.get_text(" ", strip=True))
        if not name or not duty or name in seen:
            continue
        detail_url = urljoin(final_url or source_url, str(link.get("href", "")))
        if detail_url == source_url:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；link=a[title*=自治区民委][href]；"
                    "fields=title姓名+职务；detail=link_href；order=dom"
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
