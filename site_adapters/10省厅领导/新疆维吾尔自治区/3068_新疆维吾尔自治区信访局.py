from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3068",
    "page_type": "职务分组名单页",
    "structure_group": "xinjiang_petitions_duty_name_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_xinjiang_petitions_duty_name_list_v1",
    "leader_region_selector": "ul.tyl-main-right-list-a > li",
    "name_selector": "ul.tyl-main-right-list-a > li a[target='_blank'][href]",
    "duty_selector": "ul.tyl-main-right-list-a > li a[target='_blank'][href]",
    "detail_link_selector": "ul.tyl-main-right-list-a > li a[target='_blank'][href]",
    "content_scope": {
        "start_anchor": "领导简历首项",
        "end_anchor": "领导简历末项",
        "include_selectors": ["ul.tyl-main-right-list-a > li"],
        "exclude_selectors": ["日期链接", "页脚联系方式", "新闻人物"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_item_dynamic_link",
        "detail_collector_type": "static_http",
        "detail_link_selector": "ul.tyl-main-right-list-a > li a[target='_blank'][href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "每项包含同URL日期链接和职务：姓名标题链接；只解析target=_blank标题，保持列表DOM顺序",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "ul.tyl-main-right-list-a > li",
            "name_selector": "a[target='_blank'][href]冒号后姓名",
            "duty_selector": "a[target='_blank'][href]冒号前职务",
            "detail_link_selector": "a[target='_blank'][href]",
            "content_scope": {
                "start_anchor": "领导简历首项",
                "end_anchor": "领导简历末项",
                "include_selectors": ["ul.tyl-main-right-list-a > li"],
                "exclude_selectors": ["日期链接", "页脚联系方式", "新闻人物"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML领导简历列表直接提供职务、姓名和人物详情链接"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "tyl-main-right-list-a" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _detail_url(base_url: str, href: str) -> str:
    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return ""
    resolved = urljoin(base_url, href)
    if resolved.split("#", 1)[0].rstrip("/") == base_url.split("#", 1)[0].rstrip("/"):
        return ""
    parsed = urlparse(resolved)
    return resolved if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select("ul.tyl-main-right-list-a > li"):
        if _is_hidden(item):
            continue
        link = item.select_one("a[target='_blank'][href]")
        if link is None:
            continue
        source_text = _clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?)[：:]\s*([\u4e00-\u9fff·.]{2,30})", source_text)
        if match is None:
            continue
        duty = _clean_text(match.group(1))
        name = re.sub(r"\s+", "", match.group(2))
        if not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": _detail_url(base_url, str(link.get("href", ""))),
                "evidence": duty,
                "parser": "custom_xinjiang_petitions_duty_name_list_v1",
                "selector_summary": "领导列表target=_blank标题；冒号前职务、后姓名",
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
