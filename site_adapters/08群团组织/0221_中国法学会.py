from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0221",
    "page_type": "人物列表完整页",
    "structure_group": "中国法学会领导卡片与副会长名单",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_chinalaw_leader_list_v2",
    "leader_region_selector": "div.container div.col-span-4",
    "name_selector": "领导卡片职务姓名标题；副会长名单 a",
    "duty_selector": "领导卡片标题冒号前文本；副会长分组标题",
    "detail_link_selector": "领导卡片与副会长名单中的人物文章链接",
    "risk_flag": "页面含嵌套a标签，按人物卡片和副会长分组边界解析",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理页面排版空白，并合并姓名中的全角空格。"""
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", "")).strip()


def is_name(value: str) -> bool:
    """校验当前强结构节点中的中文姓名。"""
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_text(value)))


def append_row(
    rows: list[dict],
    seen: set[tuple[str, str]],
    page_rule: dict,
    name: str,
    duty: str,
    detail_href: str,
    final_url: str,
) -> None:
    """按页面顺序追加经强结构验证的人物记录。"""
    name = clean_text(name)
    duty = clean_text(duty)
    if not is_name(name) or not duty:
        return
    key = (name, duty)
    if key in seen:
        return
    seen.add(key)
    rows.append(
        {
            "organization": page_rule["organization"],
            "url": page_rule["url"],
            "name": name,
            "duty": duty,
            "detail_url": urljoin(final_url, detail_href) if detail_href else "",
            "evidence": duty,
            "confidence": "high",
            "parser": "page_inline_chinalaw_leader_list_v2",
            "selector_summary": (
                "strategy=custom_parse_page；cards=中国法学会领导区li职务姓名标题；"
                "vice=副会长（按姓名笔划为序）同级名单a"
            ),
        }
    )


def find_leader_region(soup: BeautifulSoup) -> Tag | None:
    """以中国法学会领导标题定位最小人物内容区。"""
    for title in soup.find_all(string=lambda value: value and clean_text(value) == "中国法学会领导"):
        if not isinstance(title.parent, Tag) or not isinstance(title.parent.parent, Tag):
            continue
        region = title.parent.parent
        if region.find("ul", recursive=False) and region.find(
            string=lambda value: value and "副会长（按姓名笔划为序）" in clean_text(value)
        ):
            return region
    return None


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """解析核心领导卡片及其后的副会长名单。"""
    soup = BeautifulSoup(html, "html.parser")
    region = find_leader_region(soup)
    if region is None:
        raise RuntimeError("未定位到中国法学会领导内容区")

    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    card_pattern = re.compile(r"^(.{1,30})[:：]\s*([\u4e00-\u9fff·\u3000\s]{2,8})$")

    card_list = region.find("ul", recursive=False)
    if isinstance(card_list, Tag):
        for item in card_list.find_all("li", recursive=False):
            title_node = item.find(
                "div",
                string=lambda value: value and bool(card_pattern.fullmatch(clean_text(value))),
            )
            if not isinstance(title_node, Tag):
                continue
            match = card_pattern.fullmatch(clean_text(title_node.get_text(" ", strip=True)))
            if not match:
                continue
            link = item.find("a", href=True)
            append_row(
                rows,
                seen,
                page_rule,
                match.group(2),
                match.group(1),
                str(link.get("href") or "") if isinstance(link, Tag) else "",
                final_url,
            )

    vice_header = region.find(
        string=lambda value: value and "副会长（按姓名笔划为序）" in clean_text(value)
    )
    vice_section = vice_header.parent.parent if vice_header and isinstance(vice_header.parent, Tag) else None
    if isinstance(vice_section, Tag):
        for link in vice_section.find_all("a", href=True):
            append_row(
                rows,
                seen,
                page_rule,
                link.get_text(" ", strip=True),
                "副会长",
                str(link.get("href") or ""),
                final_url,
            )

    if not rows:
        raise RuntimeError("中国法学会领导内容区未抽取到人物")
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
