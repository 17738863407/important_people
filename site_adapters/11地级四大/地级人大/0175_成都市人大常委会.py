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
    "rule_id": "0175",
    "page_type": "职务分组名单页",
    "structure_group": "chengdu_renda_grouped_leader_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "chengdu_renda_grouped_leader_v1",
    "leader_region_selector": ".leader-wrap .other-leader",
    "name_selector": ".zr-box span.name",
    "duty_selector": ".lm-title",
    "detail_link_selector": "span.name[onclick]",
    "content_scope": {
        "include_selectors": [".leader-wrap .other-leader"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "onclick_link_only",
        "detail_link_selector": "span.name[onclick]",
        "max_detail_links": 20,
    },
    "risk_flag": "外层和内层同类名造成嵌套重复，主任onclick链接含异常空白",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value).strip()


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def _onclick_detail_url(onclick: str, final_url: str, entry_url: str) -> str:
    """只接受onclick中无空白、可验证的location地址。"""
    match = re.search(r"location(?:\.href)?\s*=\s*(['\"])(.*?)\1", onclick)
    if match is None:
        return ""
    raw_url = match.group(2)
    if "&nbsp;" in raw_url or re.search(r"\s", raw_url):
        return ""
    candidate = urljoin(final_url, raw_url)
    if _normalize_url(candidate) == _normalize_url(entry_url):
        return ""
    return candidate


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析最内层领导区，并按职务标题与人物盒子的原始顺序输出。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = []
    for candidate in soup.select(".leader-wrap .other-leader"):
        has_direct_nested_region = any(
            "other-leader" in child.get("class", [])
            for child in candidate.find_all("div", recursive=False)
        )
        if candidate.select_one("span.name") and not has_direct_nested_region:
            regions.append(candidate)
    if len(regions) != 1:
        return []
    region = regions[0]

    entry_url = page_rule["url"]
    records: list[object] = []
    current_duty = ""
    seen: set[tuple[str, str]] = set()
    for node in region.find_all(["div", "span"], recursive=False):
        classes = node.get("class", [])
        if "lm-title" in classes:
            title = _clean_text(node.get_text(" ", strip=True))
            current_duty = title if title in {"主任", "副主任", "秘书长"} else ""
            continue
        if "zr-box" not in classes or not current_duty:
            continue
        for name_node in node.select("span.name"):
            name = _clean_text(name_node.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            key = (name, current_duty)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=entry_url,
                    name=name,
                    duty=current_duty,
                    detail_url=_onclick_detail_url(
                        name_node.get("onclick", ""), final_url, entry_url
                    ),
                    evidence=current_duty,
                    confidence="high",
                    parser=page_rule["parser"],
                    selector_summary="最内层.other-leader：.lm-title + .zr-box span.name",
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
