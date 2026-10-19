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
    "rule_id": "0072",
    "page_type": "人物列表完整页",
    "structure_group": "安徽广播电视台领导正文卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_ahrtv_leader_article_cards_v1",
    "leader_region_selector": ".article_main",
    "name_selector": "人物块正文第一个非空p",
    "duty_selector": "人物块正文第二个非空p",
    "detail_link_selector": "",
    "risk_flag": "正文后含分工、简历及推荐新闻，仅取人物块前两个非空段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩正文排版空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按正文人物块顺序提取姓名和明确职务段落。"""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(".article_main")
    if article is None:
        raise RuntimeError("未定位到安徽广播电视台领导正文")

    rows: list[dict] = []
    for block in article.find_all("div", recursive=False):
        paragraphs = [
            clean_text(node.get_text(" ", strip=True))
            for node in block.select("p")
            if clean_text(node.get_text(" ", strip=True))
        ]
        if len(paragraphs) < 2:
            continue
        name, duty = paragraphs[0], paragraphs[1]
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty.startswith("安徽广播电视台"):
            continue
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_ahrtv_leader_article_cards_v1",
                "selector_summary": (
                    "strategy=custom_parse_page；scope=.article_main；"
                    "card=直属div且前两个非空p为姓名和安徽广播电视台职务"
                ),
            }
        )
    if not rows:
        raise RuntimeError("安徽广播电视台领导正文未抽取到人物")
    return rows


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
