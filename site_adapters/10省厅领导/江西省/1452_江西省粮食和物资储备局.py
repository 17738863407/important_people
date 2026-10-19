from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1452",
    "domain": "lswz.jiangxi.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jiangxi_grain_profile_biography_blocks_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "article_profile_direct",
    "collector": "static_http",
    "parser": "page_inline_jiangxi_grain_profile_biography_blocks_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "头像、姓名、短职务、简历和分工为相邻子节点；只接收直接简历块现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白，但保留原始字段标点。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按正文直接子节点顺序提取简历块姓名和完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("article.SinglePage")
    if region is None:
        return []
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for node in region.children:
        if not isinstance(node, Tag):
            continue
        text = clean_text(node.get_text(" ", strip=True))
        name_match = re.search(r"简历[：:]\s*([\u3400-\u9fff·]{2,5})[，,]", text)
        duty_match = re.search(r"现任[^。]*。", text)
        if name_match is None or duty_match is None:
            continue
        name = name_match.group(1)
        evidence = re.sub(r"^现任\s*", "", clean_text(duty_match.group(0))).removesuffix("。").strip()
        if name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；region=article.SinglePage；"
                    "item=direct-child-biography-block；"
                    "name=after-简历；duty=scoped-current-sentence"
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
