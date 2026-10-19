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
    "rule_id": "1700",
    "page_type": "人物列表完整页",
    "structure_group": "xinjiang_mpa_zx_right_title_links",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_xinjiang_mpa_zx_right_title_links_v1",
    "leader_region_selector": ".zx_right h3",
    "name_selector": ".zx_right h3 a[href]",
    "duty_selector": ".zx_right h3 a[href]",
    "detail_link_selector": ".zx_right h3 a[href]",
    "content_scope": {
        "start_anchor": "首个可见领导标题",
        "end_anchor": "末个可见领导标题",
        "include_selectors": [".zx_right h3 a[href]"],
        "exclude_selectors": ["隐藏节点", "非领导栏目"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_item_dynamic_link",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".zx_right h3 a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "标题文本为职务、姓名合并字段，须以中文冒号为边界且保持DOM原始顺序",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".zx_right h3",
            "name_selector": "a[href]标题冒号后的姓名",
            "duty_selector": "a[href]标题冒号前的职务",
            "detail_link_selector": ".zx_right h3 a[href]",
            "content_scope": {
                "start_anchor": "首个可见标题",
                "end_anchor": "末个可见标题",
                "include_selectors": [".zx_right h3 a[href]"],
                "exclude_selectors": ["隐藏节点"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML标题直接提供姓名、职务与人物详情链接"},
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
    for link in soup.select(".zx_right h3 a[href]"):
        if _is_hidden(link):
            continue
        source_text = _clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?)[：:]\s*([\u4e00-\u9fff·]{2,12})", source_text)
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
                "parser": "custom_xinjiang_mpa_zx_right_title_links_v1",
                "selector_summary": ".zx_right h3 a[href]；冒号前职务、后姓名",
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
