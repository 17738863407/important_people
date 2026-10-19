from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3780",
    "domain": "www.tianshui.gov.cn",
    "page_type": "同页四套班子交错分组列表",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_tianshui_party_leaders_v1",
    "leader_region_selector": ".leader",
    "name_selector": ".item .picBox li a",
    "duty_selector": ".item > h2, .item01 .txt p",
    "detail_link_selector": ".item .picBox li a[href]",
    "content_scope": {"start_anchor": "市委领导", "end_anchor": "市人大常委会领导", "include_selectors": [".leader"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "市委与政府分组交错展示，只接受市委相关分组并合并重复人物兼职",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理页面排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按网页次序解析市委相关分组，并合并同一人物的多项现职。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".leader")
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    accepted = {"市委领导", "副书记", "市委常委", "市委秘书长"}
    ordered: dict[str, dict[str, object]] = {}
    for item in region.select(":scope > .item"):
        heading = item.select_one(":scope > h2")
        group = clean_text(heading.get_text(" ", strip=True) if heading else "")
        if group not in accepted:
            continue
        for link in item.select(".picBox li a[href]"):
            name_node = link.select_one("h4, :scope > p")
            if not name_node:
                continue
            name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True)))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            duty_node = link.select_one(".txt p") if group == "市委领导" else None
            duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else group
            record = ordered.setdefault(name, {"duties": [], "url": urljoin(base_url, str(link.get("href", "")))})
            duties = record["duties"]
            if isinstance(duties, list) and duty not in duties:
                duties.append(duty)
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
