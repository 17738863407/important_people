from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3652",
    "page_type": "职务分组名单页",
    "structure_group": "ouc_current_leader_grouped_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ouc_current_leader_grouped_list_v1",
    "leader_region_selector": "div.ld",
    "name_selector": ".nameList .name",
    "duty_selector": ":scope > .career:not(.hidden)",
    "detail_link_selector": ".nameList .name a[href]",
    "content_scope": {
        "include_selectors": ["div.ld"],
        "exclude_selectors": [".hidden"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_link_only",
        "detail_link_selector": ".nameList .name a[href]",
        "max_detail_links": 50,
    },
    "risk_flag": "页面含隐藏的重复党委常委分组，同一人物可能分属多个职务组",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """清除纯排版空白，不改变网页职务语义。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def _normalize_url(url: str) -> str:
    """仅用于判断详情链接是否与入口页相同。"""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def _is_hidden(node: object) -> bool:
    """排除当前节点及祖先中明确标记为隐藏的备用DOM。"""
    current = node
    while current is not None:
        classes = {str(item).lower() for item in current.get("class", [])} if hasattr(current, "get") else set()
        style = str(current.get("style", "")).replace(" ", "").lower() if hasattr(current, "get") else ""
        if (
            "hidden" in classes
            or "display:none" in style
            or (hasattr(current, "has_attr") and current.has_attr("hidden"))
            or (hasattr(current, "get") and str(current.get("aria-hidden", "")).lower() == "true")
        ):
            return True
        current = getattr(current, "parent", None)
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按可见职务组顺序解析，并按人物首次出现顺序聚合多项职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    entry_url = page_rule["url"]
    people: dict[str, dict[str, object]] = {}
    for group in soup.select("div.ld"):
        if _is_hidden(group):
            continue
        duty_node = group.select_one(":scope > .career:not(.hidden)")
        if duty_node is None or _is_hidden(duty_node):
            continue
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        if not duty:
            continue

        for name_node in group.select(".nameList .name"):
            if _is_hidden(name_node):
                continue
            anchor = name_node.select_one("a[href]")
            raw_name = anchor.get_text(" ", strip=True) if anchor is not None else name_node.get_text(" ", strip=True)
            name = _clean_text(raw_name).rstrip("、，,；;")
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            href = str(anchor.get("href", "")).strip() if anchor is not None else ""
            candidate = urljoin(final_url, href)
            detail_url = ""
            if (
                href
                and not href.lower().startswith(("#", "javascript:", "mailto:"))
                and _normalize_url(candidate) != _normalize_url(entry_url)
            ):
                detail_url = candidate

            person = people.setdefault(name, {"duties": [], "detail_url": detail_url})
            duties = person["duties"]
            if duty not in duties:
                duties.append(duty)
            if not person["detail_url"] and detail_url:
                person["detail_url"] = detail_url

    records: list[object] = []
    for name, person in people.items():
        duty = "；".join(person["duties"])
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=entry_url,
                name=name,
                duty=duty,
                detail_url=person["detail_url"],
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="div.ld: .career:not(.hidden) + .nameList .name a[href]",
            )
        )
    return records


def main(update_fetch_memory: bool) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=update_fetch_memory)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    should_update_fetch_memory = False
    main(should_update_fetch_memory)
