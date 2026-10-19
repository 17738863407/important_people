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
    "rule_id": "3786",
    "domain": "www.zhangye.gov.cn",
    "page_type": "同页市委市政府分组列表",
    "load_mode": "浏览器渲染DOM",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_inline_zhangye_party_leaders_v1",
    "leader_region_selector": ".zy-ldzc .ldzcItem",
    "name_selector": ".ldnm, .ldzclist .nm",
    "duty_selector": ".ldzw, .tabnav1 .tabn",
    "detail_link_selector": "a[href]",
    "content_scope": {"start_anchor": "市委领导", "end_anchor": "市政府领导", "include_selectors": [".zy-ldzc"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "同页另有市政府分组；同一人物可能同时为常委和秘书长",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理页面排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析左侧市委分组，并按首次出现顺序合并兼职。"""
    soup = BeautifulSoup(html, "html.parser")
    groups = soup.select(".zy-ldzc .ldzcItem")
    region = next((item for item in groups if clean_text((item.select_one(".swld") or item).get_text(" ", strip=True)).startswith("市委领导")), None)
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    ordered: dict[str, dict[str, object]] = {}
    primary_name = region.select_one(".ldzp .ldnm")
    primary_duty = region.select_one(".ldzp .ldzw")
    primary_link = primary_name.find_parent("a") if primary_name else None
    if primary_name and primary_duty:
        name = re.sub(r"\s+", "", clean_text(primary_name.get_text(" ", strip=True)))
        ordered[name] = {"duties": [clean_text(primary_duty.get_text(" ", strip=True))], "url": urljoin(base_url, str(primary_link.get("href", ""))) if primary_link else ""}
    current_duty = ""
    for child in region.children:
        if not isinstance(child, Tag):
            continue
        if "tabnav1" in (child.get("class") or []):
            current_duty = clean_text(child.get_text(" ", strip=True))
            continue
        if "ldzr" not in (child.get("class") or []) or not current_duty:
            continue
        for link in child.select(".ldzclist li a[href]"):
            name_node = link.select_one(".nm")
            name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            record = ordered.setdefault(name, {"duties": [], "url": urljoin(base_url, str(link.get("href", "")))})
            duties = record["duties"]
            if isinstance(duties, list) and current_duty not in duties:
                duties.append(current_duty)
    rows: list[dict[str, str]] = []
    for name, record in ordered.items():
        duties = record["duties"]
        if not isinstance(duties, list) or not duties:
            continue
        duty = "；".join(str(part) for part in duties)
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": str(record["url"]), "confidence": "high", "parser": str(page_rule.get("parser", ""))})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
