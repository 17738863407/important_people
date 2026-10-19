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
    "rule_id": "2853",
    "domain": "wb.jiangsu.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jiangsu_foreign_affairs_leader_list_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_jiangsu_foreign_affairs_leader_list_v2",
    "detail_strategy": {"required": False, "mode": "dynamic_from_list"},
    "risk_flag": "隐藏访问计数iframe排除；列表项正文包含姓名与职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def compact_name(value: str) -> str:
    """移除姓名中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导列表DOM顺序提取链接姓名、同行职务和独立人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(".main-content-right li.ldlist"):
        link = item.select_one("a[href][title]")
        if link is None:
            continue
        name = compact_name(str(link.get("title", "")))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or name in seen:
            continue
        item_text = clean_text(item.get_text(" ", strip=True))
        duty_match = re.fullmatch(rf"{re.escape(name)}\s+(.+)", item_text)
        if duty_match is None:
            continue
        duty = clean_text(duty_match.group(1))
        if not duty:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, str(link.get("href", ""))),
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=.main-content-right li.ldlist；"
                    "name=a[href][title]；duty=list-item-text-after-name"
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
