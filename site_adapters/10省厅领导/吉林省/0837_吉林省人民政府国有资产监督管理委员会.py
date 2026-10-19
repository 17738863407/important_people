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
    "rule_id": "0837",
    "domain": "gzw.jl.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "jilin_sasac_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_jilin_sasac_leader_cards_v2",
    "detail_strategy": {"required": False, "mode": "inline_with_verified_links"},
    "risk_flag": "title末尾挂职括注属于职务修饰，必须从姓名移回职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def split_compound_title(value: str) -> tuple[str, str]:
    """拆分“职务 姓名”，并把姓名后的括注归回职务。"""
    title = clean_text(value)
    match = re.fullmatch(r"(.+?)\s+([\u3400-\u9fff·]{2,5})(（[^）]+）)?", title)
    if match is None:
        return "", ""
    duty = clean_text(match.group(1))
    name = match.group(2)
    suffix = match.group(3) or ""
    evidence = re.sub(r"[（(]\s*挂职\s*[）)]", "", f"{duty}{suffix}").strip()
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片DOM顺序读取复合标题和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for card in soup.select(".ej_ld"):
        link = card.select_one(".ej_ld_txt h2 a[href]")
        if link is None:
            continue
        name, duty = split_compound_title(str(link.get("title", "")) or link.get_text(" ", strip=True))
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, str(link.get("href", ""))),
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；row=.ej_ld；"
                    "field=.ej_ld_txt h2 a[title] duty-name；detail=same-link"
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
