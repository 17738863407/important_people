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
    "rule_id": "2476",
    "page_type": "多人物详情合并页",
    "structure_group": "yunnan_academy_current_leader_links",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http_with_browser_fallback",
    "parser": "custom_yunnan_academy_current_leader_links_v2",
    "leader_region_selector": "div#mainBody",
    "name_selector": "li a[href]标题冒号后文本",
    "duty_selector": "li a[href]标题冒号前文本",
    "detail_link_selector": "li a[href]",
    "content_scope": {
        "start_anchor": "现任领导",
        "end_anchor": "页面列表末尾",
        "include_selectors": ["div#mainBody li a[href]"],
        "exclude_selectors": ["栏目导航", "历任领导", "友情链接", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_links_only",
        "detail_collector_type": "static_http",
        "detail_link_selector": "li a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 30,
    },
    "risk_flag": "权威业务入口当前SSL协议异常；只接受现任领导目录中结构明确的职务：姓名链接，不使用历史名单兜底",
    "confidence": "medium",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div#mainBody",
            "name_selector": "li a[href]标题冒号后文本",
            "duty_selector": "li a[href]标题冒号前文本",
            "detail_link_selector": "li a[href]",
            "content_scope": {
                "start_anchor": "现任领导",
                "end_anchor": "页面列表末尾",
                "include_selectors": ["div#mainBody li a[href]"],
                "exclude_selectors": ["栏目导航", "历任领导", "友情链接", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "目录页人物链接标题直接提供职务和姓名"},
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
        if str(current.get("id", "")) == "mainBody":
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div#mainBody")
    if region is None or _is_hidden(region):
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in region.select("li a[href]"):
        if _is_hidden(link):
            continue
        text = _clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        parts = re.split(r"[：:]", text, maxsplit=1)
        if len(parts) != 2:
            continue
        duty = _clean_text(parts[0]).strip(" ：:，,。.；;")
        name = re.sub(r"\s+", "", _clean_text(parts[1])).strip(" ：:，,。.；;")
        href = str(link.get("href") or "").strip()
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, href) if href and not href.startswith(("#", "javascript:", "mailto:")) else ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_yunnan_academy_current_leader_links_v2",
                "selector_summary": "div#mainBody li a[href]；标题冒号前职务；冒号后姓名",
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
