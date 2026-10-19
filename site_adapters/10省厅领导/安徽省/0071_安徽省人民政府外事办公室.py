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
    "rule_id": "0071",
    "page_type": "人物列表完整页",
    "structure_group": "安徽省外办政务公开领导列表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_ahfao_leader_title_suffix_name_v2",
    "leader_region_selector": "#xxgk_lmcon ul.xxgk_nav_list",
    "name_selector": "li.clearfix a.title[href]文本尾部",
    "duty_selector": "li.clearfix a.title[href]文本姓名前部",
    "detail_link_selector": "li.clearfix a.title[href]",
    "risk_flag": "online会丢失catId；列表另含成员及分工介绍汇总链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    """去除短标题中的排版空白。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def split_duty_name(value: str) -> tuple[str, str]:
    """按职务结尾关键词与中文姓名后缀拆分标题。"""
    text = compact_text(value)
    if "介绍" in text or "分工" in text:
        return "", ""
    match = re.fullmatch(r"(?P<duty>.+(?:主任|巡视员|书记))(?P<name>[\u4e00-\u9fff]{2,4})", text)
    if not match:
        return "", ""
    return match.group("duty"), match.group("name")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按政务公开列表顺序解析安徽省外办领导。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for link in soup.select("#xxgk_lmcon ul.xxgk_nav_list > li.clearfix a.title[href]"):
        duty, name = split_duty_name(link.get_text(" ", strip=True))
        if not duty or not name:
            continue
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_ahfao_leader_title_suffix_name_v2",
                "selector_summary": (
                    "strategy=custom_parse_page；region=#xxgk_lmcon ul.xxgk_nav_list；"
                    "item=li.clearfix a.title[href]；split=职务结尾关键词+姓名后缀"
                ),
            }
        )
    if not rows:
        raise RuntimeError("安徽省外办领导列表未抽取到人物")
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
