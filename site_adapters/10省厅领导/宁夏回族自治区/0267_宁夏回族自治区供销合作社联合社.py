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
    "rule_id": "0267",
    "domain": "coop.nx.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_window_text_links_duty_name_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_inline_leader_window_text_links_duty_name_v1",
    "leader_link_selector": "a.a[href]",
    "detail_strategy": {"required": False, "mode": "card_link"},
    "risk_flag": "当前权威名单已核验为HTML文本链接而非图片；以职务+姓名标签格式排除站点Logo链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩列表标签中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_label(value: object) -> tuple[str, str]:
    """从“职务 姓名”标签末尾动态拆分姓名。"""
    text = clean_text(value)
    match = re.fullmatch(r"(.+?)\s+([\u3400-\u9fff·]{2,8})", text)
    if match is None:
        return "", ""
    return clean_text(match.group(1)), re.sub(r"\s+", "", match.group(2))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导之窗HTML链接顺序提取职务、姓名和独立详情页。"""
    soup = BeautifulSoup(html or "", "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(str(page_rule.get("leader_link_selector", ""))):
        duty, name = parse_label(link.get_text(" ", strip=True))
        if not duty or not name or name in seen:
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
                    "strategy=custom_parse_page；link=a.a[href]；"
                    "label=职务+末尾姓名；detail=link_href；order=dom"
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
