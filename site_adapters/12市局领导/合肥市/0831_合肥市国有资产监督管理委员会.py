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
    "rule_id": "0831",
    "page_type": "图片人物简介页",
    "structure_group": "leader_image_followed_by_biography_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom_parse_page",
    "collector": "browser_dom",
    "parser": "page_inline_image_followed_by_biography_v1",
    "leader_region_selector": "div.wzcon.j-fontContent",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口首次响应可能为521；仅取每张人物头像后、下一张头像前的首个简介段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


ROLE_NAME_PATTERN = re.compile(
    r"^(?P<duty>党委委员、副主任|党委委员、驻市国资委纪检监察组组长|总经济师|二级调研员)"
    r"(?P<name>[\u3400-\u9fff·]{2,4})，(?:男|女)，"
)


def clean_text(value: object) -> str:
    """只清理网页排版空白，不改写原始职务。"""
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按头像DOM顺序解析其后首个简介段落，排除分工和联系电话。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    children = [child for child in region.children if isinstance(child, Tag)]
    for index, node in enumerate(children):
        if node.name != "p" or node.find("img") is None:
            continue

        biography = ""
        for candidate in children[index + 1 :]:
            if candidate.name == "p" and candidate.find("img") is not None:
                break
            text = clean_text(candidate.get_text(" ", strip=True))
            if text:
                biography = text
                break
        if not biography:
            continue

        match = ROLE_NAME_PATTERN.match(biography)
        if match is None:
            continue
        name = match.group("name")
        evidence = match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "div.wzcon.j-fontContent；人物头像p img；"
                    "头像后且下一头像前首个非空p；履历首行职务+姓名+性别边界"
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
