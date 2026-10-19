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
    "rule_id": "0632",
    "domain": "gat.jiangsu.gov.cn",
    "page_type": "人物目录详情页",
    "structure_group": "jiangsu_police_jpage_list_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "browser_dom",
    "parser": "page_inline_jiangsu_police_jpage_list_detail_v1",
    "leader_region_selector": "[id='406002'] li.fdzdgknr-lb",
    "name_selector": "a[title][href]",
    "detail_link_selector": "a[title][href]",
    "detail_strategy": {
        "required": True,
        "mode": "online_current_detail",
        "fetch_mode": "online",
        "content_selector": ".ldxx-right .ldxx-jj",
        "evidence_pattern": r"现任[^。]*。",
    },
    "risk_flag": "列表由jpage脚本渲染；原始职务只取对应详情页简介区的完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩网页排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """移除姓名中的排版空白，不改变姓名字符。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\u00a0]+", "", str(value or ""))


def fetch_detail_html(detail_url: str, fetch_mode: str) -> str:
    """通过项目公共采集器在线取得人物详情页。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    result = fetch_html_with_strategy(detail_url, strategy=fetch_mode)
    return result.html


def extract_evidence(detail_html: str, name: str, strategy: dict) -> str:
    """仅在当前人物详情页简介区提取完整“现任……”原句。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    region = soup.select_one(str(strategy["content_selector"]))
    if region is None:
        return ""
    intro = clean_text(region.get_text(" ", strip=True))
    if not intro or not intro.startswith(name):
        return ""
    match = re.search(str(strategy["evidence_pattern"]), intro)
    return re.sub(r"^现任\s*", "", match.group(0)).rstrip("。 ") if match is not None else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按当前列表顺序在线取得详情页中的现任职务依据。"""
    soup = BeautifulSoup(html, "html.parser")
    strategy = dict(page_rule["detail_strategy"])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    errors: list[str] = []

    for item in soup.select(str(page_rule["leader_region_selector"])):
        link = item.select_one(str(page_rule["detail_link_selector"]))
        name = clean_name(link.get_text(" ", strip=True) if link else "")
        if link is None or not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        try:
            detail_html = fetch_detail_html(detail_url, str(strategy["fetch_mode"]))
            evidence = extract_evidence(detail_html, name, strategy)
        except Exception as error:
            errors.append(f"{name}详情页采集失败：{error}")
            continue
        if not evidence:
            errors.append(f"{name}详情页简介区未取得现任职务原句")
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
            }
        )

    if errors:
        raise RuntimeError("；".join(errors))
    if not rows:
        raise RuntimeError("当前领导列表未解析到有效人物")
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
