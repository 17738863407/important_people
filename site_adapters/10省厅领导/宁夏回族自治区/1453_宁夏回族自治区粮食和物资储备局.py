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
    "rule_id": "1453",
    "domain": "lswz.nx.gov.cn",
    "page_type": "人物表格页",
    "structure_group": "leader_table_image_alt_name_duty_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_inline_leader_table_image_alt_name_duty_v1",
    "leader_region_selector": "table.leaderIntro",
    "leader_image_selector": "img[alt]",
    "detail_strategy": {"required": False, "mode": "image_parent_link"},
    "risk_flag": "图片为人物头像，姓名与职务由img alt/title HTML字段直接承载；无外层href时详情留空",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩alt/title字段中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def split_alt(value: object) -> tuple[str, str]:
    """从头像“姓名 职务”alt/title字段动态拆分强字段。"""
    text = clean_text(value)
    match = re.fullmatch(r"([\u3400-\u9fff·]{2,8})\s+(.+)", text)
    if match is None:
        return "", ""
    return re.sub(r"\s+", "", match.group(1)), clean_text(match.group(2))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导表格头像DOM顺序提取alt强字段和外层详情链接。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for image in region.select(str(page_rule.get("leader_image_selector", ""))):
        name, duty = split_alt(image.get("alt") or image.get("title") or "")
        if not name or not duty or name in seen:
            continue
        link = image.find_parent("a", href=True)
        detail_url = urljoin(final_url or source_url, str(link.get("href", ""))) if link else ""

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
                    "strategy=custom_parse_page；region=table.leaderIntro；"
                    "fields=img alt/title姓名+职务；detail=parent_a_href"
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
