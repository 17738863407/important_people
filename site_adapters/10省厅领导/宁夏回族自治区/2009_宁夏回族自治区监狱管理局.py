from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2009",
    "domain": "nxjy.nx.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_article_profile_semicolon_duty_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_inline_leader_article_profile_semicolon_duty_paragraphs_v1",
    "content_selector": ".view",
    "paragraph_selector": "p",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "站点HTTPS证书过期，使用公共raw_http增强采集器SSL降级；每人段落按姓名/个人信息/分号后职务拆分",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """归一HTML排版空白，不改变职务语义。"""
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    return re.sub(r"\s+([，。、；：）])", r"\1", text)


def parse_profile_paragraph(value: object) -> tuple[str, str]:
    """从“姓名，个人信息；职务。”段落中提取姓名和职务。"""
    text = clean_text(value)
    match = re.fullmatch(r"([\u3400-\u9fff·]{2,8})，.+?；\s*(自治区[^。]+)。", text)
    if match is None:
        return "", ""
    return match.group(1), clean_text(match.group(2))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导正文人物段落顺序动态提取姓名和职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("content_selector", "")))
    if region is None:
        return []

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select(str(page_rule.get("paragraph_selector", ""))):
        name, duty = parse_profile_paragraph(paragraph.get_text(" ", strip=True))
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；region=.view；paragraph=p；"
                    "pattern=姓名，个人信息；自治区职务。；detail=none"
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
