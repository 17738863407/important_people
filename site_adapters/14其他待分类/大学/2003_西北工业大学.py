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
    "rule_id": "2003",
    "page_type": "职务分组名单页",
    "structure_group": "nwpu_current_leader_grouped_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "nwpu_current_leader_grouped_list_v1",
    "leader_region_selector": ".main-public-con-right-lingdao-con .leader-grid-container",
    "name_selector": ".leader-item .leader-names a[href]",
    "duty_selector": ".leader-item .leader-post",
    "detail_link_selector": ".leader-item .leader-names a[href]",
    "content_scope": {
        "include_selectors": [".main-public-con-right-lingdao-con .leader-grid-container"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_link_only",
        "detail_link_selector": ".leader-item .leader-names a[href]",
        "max_detail_links": 50,
    },
    "risk_flag": "同一人物分属多个职务组，需按首次出现顺序聚合",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_name(text: str) -> str:
    """清除姓名中的展示性空白，并保留中文间隔号。"""
    return re.sub(r"\s+", "", text).strip()


def _clean_role_text(text: str) -> str:
    """清除职务内部为排版插入的全角及不换行空白。"""
    return re.sub(r"\s+", "", text).strip()


def _normalize_url(url: str) -> str:
    """移除片段标识，便于识别等同于入口页的链接。"""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def _extract_duty(item: object) -> str:
    """从职务节点提取主职务和独立的补充职务。"""
    post = item.select_one(".leader-post")
    if post is None:
        return ""

    parts: list[str] = []
    direct_text = "".join(str(node) for node in post.find_all(string=True, recursive=False))
    direct_text = _clean_role_text(direct_text)
    if direct_text:
        parts.append(direct_text)

    for child in post.select(":scope > .leader-post-sub"):
        child_text = _clean_role_text(child.get_text(" ", strip=True))
        if child_text and child_text not in parts:
            parts.append(child_text)
    return "；".join(parts)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按页面职务组顺序解析人物，并聚合同一人物的多个职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".main-public-con-right-lingdao-con .leader-grid-container")
    if region is None:
        return []

    entry_url = page_rule["url"]
    people: dict[str, dict[str, object]] = {}
    for item in region.select(".leader-item"):
        duty = _extract_duty(item)
        if not duty:
            continue
        for anchor in item.select(".leader-names a[href]"):
            name = _clean_name(anchor.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue

            href = anchor.get("href", "").strip()
            detail_url = urljoin(final_url, href)
            if (
                not href
                or href.startswith(("#", "javascript:", "mailto:"))
                or _normalize_url(detail_url) == _normalize_url(entry_url)
            ):
                detail_url = ""

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
                selector_summary=".leader-item: .leader-post + .leader-names a[href]",
            )
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
