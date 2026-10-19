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
    "rule_id": "2018",
    "domain": "nyj.jl.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jilin_energy_leader_info_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_jilin_energy_leader_info_cards_v2",
    "detail_strategy": {"required": False, "mode": "inline_with_verified_links"},
    "risk_flag": "增强requests误跳无障碍通道；raw_http保留leader_info人物卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()
    return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)


def clean_evidence(value: str) -> str:
    """删除无期限独立兼任状态标记，保留具体另一职务。"""
    return re.sub(r"(?:（兼）|\(兼\)|[<＜]兼[>＞])", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导信息卡片顺序读取完整职务、姓名和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(".leader_info li"):
        paragraphs = item.select(":scope > p")
        link = item.select_one("p a[href]")
        duty = clean_text(paragraphs[0].get_text(" ", strip=True) if paragraphs else "")
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True) if link else "")
        if link is None or not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": clean_evidence(duty),
                "detail_url": urljoin(final_url, str(link.get("href", ""))),
                "evidence": clean_evidence(duty),
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；row=.leader_info li；"
                    "duty=first-p；name-detail=second-p a[href]"
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
