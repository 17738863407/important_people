from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3546",
    "page_type": "职务分组名单页",
    "structure_group": "hust_current_leader_grouped_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "force_browser": True,
    "playwright_stealth_profile": 2,
    "extract_mode": "list_direct",
    "collector": "browser_fallback",
    "parser": "hust_current_leader_grouped_list_v1",
    "leader_region_selector": ".ldlist",
    "name_selector": ".ldlist ul.wow.flex > li .names > ul > li > a",
    "duty_selector": ".ldlist ul.wow.flex > li > .tit",
    "detail_link_selector": ".ldlist ul.wow.flex > li .names a[href]",
    "content_scope": {
        "include_selectors": [".ldlist"],
        "exclude_selectors": ["[hidden]", "[aria-hidden='true']", "[style*='display: none']"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_link_only",
        "detail_link_selector": ".ldlist ul.wow.flex > li .names a[href]",
        "max_detail_links": 50,
    },
    "risk_flag": "官网阻断普通HTTP请求；同一人物分属多个职务组；页面含隐藏空职务组",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _compact_name(value: str) -> str:
    """删除官网为姓名视觉排版加入的普通空白和全角空格。"""
    return re.sub(r"[\s\u00a0\u2000-\u200f\u3000]+", "", str(value or "")).strip()


def _extract_duty(title_node: Tag) -> str:
    """按换行边界合并同一职务组标题，保留监察专员等补充职务。"""
    parts: list[str] = []
    for text in title_node.stripped_strings:
        cleaned = re.sub(r"[\s\u00a0\u2000-\u200f\u3000]+", "", str(text)).strip("、，,；;。")
        if cleaned and cleaned not in parts:
            parts.append(cleaned)
    return "；".join(parts)


def _is_hidden(node: Tag) -> bool:
    """排除当前职务组及其祖先中由属性、样式或明确类名隐藏的节点。"""
    current: Tag | None = node
    while isinstance(current, Tag):
        if current.has_attr("hidden"):
            return True
        if str(current.get("aria-hidden") or "").strip().lower() == "true":
            return True
        style = re.sub(r"\s+", "", str(current.get("style") or "")).lower()
        if "display:none" in style or "visibility:hidden" in style:
            return True
        classes = {str(item).strip().lower() for item in current.get("class", [])}
        if classes.intersection({"hidden", "hide", "dn", "none"}):
            return True
        if current.name == "div" and "ldlist" in classes:
            break
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _normalize_url(url: str) -> str:
    """忽略片段并统一主机大小写，供入口页与详情页语义判重。"""
    parts = urlsplit(str(url or "").strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def _resolve_detail_url(anchor: Tag, base_url: str, entry_url: str) -> str:
    """仅保留当前姓名节点中可验证的真实独立人物详情链接。"""
    href = str(anchor.get("href") or "").strip()
    if not href or href.lower().startswith(("#", "javascript:", "mailto:")):
        return ""
    candidate = urljoin(base_url, href)
    if _normalize_url(candidate) == _normalize_url(entry_url):
        return ""
    return candidate


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按可见职务组顺序解析，并按人物首次出现顺序聚合多项现任职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".ldlist")
    if region is None:
        return []

    entry_url = str(page_rule.get("url") or "")
    base_url = final_url or entry_url
    people: dict[str, dict[str, object]] = {}

    for item in region.select("ul.wow.flex > li"):
        if _is_hidden(item):
            continue
        title_node = item.select_one(":scope > .tit")
        names_node = item.select_one(":scope > .names")
        if title_node is None or names_node is None:
            continue
        duty = _extract_duty(title_node)
        if not duty:
            continue

        for anchor in names_node.select(":scope > ul > li > a"):
            name = _compact_name(anchor.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue

            detail_url = _resolve_detail_url(anchor, base_url, entry_url)
            person = people.setdefault(name, {"duties": [], "detail_url": detail_url})
            duties = person["duties"]
            if duty not in duties:
                duties.append(duty)
            if not person["detail_url"] and detail_url:
                person["detail_url"] = detail_url

    rows: list[dict[str, str]] = []
    selector_summary = (
        "strategy=custom_parse_page；region=.ldlist；group=ul.wow.flex > li；"
        "duty=:scope > .tit；name=.names > ul > li > a；"
        "hidden=属性/样式/类名排除；aggregation=按姓名首次出现顺序合并职务组"
    )
    for name, person in people.items():
        evidence = "；".join(person["duties"])
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": str(person["detail_url"]),
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser") or ""),
                "selector_summary": selector_summary,
            }
        )
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
