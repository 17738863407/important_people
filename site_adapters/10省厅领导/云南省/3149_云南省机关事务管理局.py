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
    "rule_id": "3149",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_goa_leader_tab_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_goa_leader_tab_list_v2",
    "leader_region_selector": "h3.tab领导简介页签后的ul.list_t",
    "name_selector": "li > a[href]首个非空文本行",
    "duty_selector": "li > a[href]第二个非空文本行",
    "detail_link_selector": "li > a[href]",
    "content_scope": {
        "start_anchor": "领导简介",
        "end_anchor": "领导简介列表末项",
        "include_selectors": ["h3.tab + ul.list_t > li"],
        "exclude_selectors": ["机构职责", "机关处室", "直属单位", "监管单位", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_links_only",
        "detail_collector_type": "static_http",
        "detail_link_selector": "li > a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
    },
    "risk_flag": "同页有多个结构相同的机构列表；必须以领导简介页签及其紧邻ul限定，不依赖职务关键词",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "h3.tab领导简介页签后的ul.list_t",
            "name_selector": "li > a[href]首个非空文本行",
            "duty_selector": "li > a[href]第二个非空文本行",
            "detail_link_selector": "li > a[href]",
            "content_scope": {
                "start_anchor": "领导简介",
                "end_anchor": "领导简介列表末项",
                "include_selectors": ["h3.tab + ul.list_t > li"],
                "exclude_selectors": ["机构职责", "机关处室", "直属单位", "监管单位", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML领导简介列表直接提供姓名、职务和详情链接"},
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
        if "list_t" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _find_leader_list(soup: BeautifulSoup) -> Tag | None:
    for heading in soup.select("h3.tab"):
        current_label = heading.select_one("a.cur")
        if _clean_text(current_label.get_text(" ", strip=True) if current_label else "") != "领导简介":
            continue
        candidate = heading.find_next_sibling("ul")
        if isinstance(candidate, Tag) and "list_t" in candidate.get("class", []):
            return candidate
    return None


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    leader_list = _find_leader_list(soup)
    if leader_list is None or _is_hidden(leader_list):
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in leader_list.find_all("li", recursive=False):
        link = item.find("a", href=True)
        if link is None or _is_hidden(link):
            continue
        lines = [_clean_text(line) for line in link.get_text("\n", strip=True).splitlines()]
        lines = [line for line in lines if line]
        if len(lines) < 2:
            continue
        name = re.sub(r"\s+", "", lines[0])
        duty = lines[1].strip(" ：:，,。.；;")
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not duty or name in seen:
            continue
        detail_url = urljoin(final_url, href) if href and not href.startswith(("#", "javascript:", "mailto:")) else ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_yunnan_goa_leader_tab_list_v2",
                "selector_summary": "领导简介h3.tab紧邻ul.list_t；链接首行姓名；第二行职务",
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
