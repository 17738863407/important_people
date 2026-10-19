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
    "rule_id": "3276",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_radio_tv_grouped_leader_lists",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_radio_tv_grouped_leader_lists_v2",
    "leader_region_selector": ".jgzz-section .section-name",
    "name_selector": "li p a[href]",
    "duty_selector": "li h5",
    "detail_link_selector": "li p a[href]",
    "content_scope": {
        "start_anchor": "局领导",
        "end_anchor": "巡视员末项",
        "include_selectors": [".jgzz-section .section-name li"],
        "exclude_selectors": ["机构职责", "机关处室", "直属单位", "导航", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_links_only",
        "detail_collector_type": "static_http",
        "detail_link_selector": "li p a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
    },
    "risk_flag": "同一h5职务可对应多个姓名链接；每个人重复使用所属li完整原始职务，不把局党组改写为机构全称",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".jgzz-section .section-name",
            "name_selector": "li p a[href]",
            "duty_selector": "li h5",
            "detail_link_selector": "li p a[href]",
            "content_scope": {
                "start_anchor": "局领导",
                "end_anchor": "巡视员末项",
                "include_selectors": [".jgzz-section .section-name li"],
                "exclude_selectors": ["机构职责", "机关处室", "直属单位", "导航", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML分组列表直接提供原始职务、姓名和详情链接"},
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
        if "section-name" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for section in soup.select(".jgzz-section .section-name"):
        if _is_hidden(section):
            continue
        for item in section.select("li"):
            duty_node = item.select_one("h5")
            duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").strip(" ：:，,。.；;")
            if not duty:
                continue
            for link in item.select("p a[href]"):
                if _is_hidden(link):
                    continue
                name = re.sub(r"\s+", "", _clean_text(link.get_text(" ", strip=True)))
                href = str(link.get("href") or "").strip()
                if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or name in seen:
                    continue
                detail_url = urljoin(final_url, href) if href and not href.startswith(("#", "javascript:", "mailto:")) else ""
                seen.add(name)
                rows.append(
                    {
                        "name": name,
                        "duty": duty,
                        "detail_url": detail_url,
                        "evidence": duty,
                        "parser": "custom_yunnan_radio_tv_grouped_leader_lists_v2",
                        "selector_summary": ".jgzz-section .section-name；li h5职务；p a[href]姓名详情",
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
