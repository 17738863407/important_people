from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3895",
    "page_type": "详情页内领导导航",
    "structure_group": "wuxi_government_detail_sidebar_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "grouped_links",
    "collector": "requests",
    "parser": "page_inline_wuxi_government_sidebar_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".sz-nav",
    "name_selector": ".sz-name-list a[href]",
    "duty_selector": ".sz-title",
    "detail_link_selector": ".sz-name-list a[href]",
    "risk_flag": "入口为现任市长详情；须限定市政府领导右侧导航，排除个人简历、分工和页脚机构链接",
    "confidence": "high",
    "filter_policy": "strict_structure",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_compact(value: object) -> str:
    """删除姓名或职务标题内部的纯排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def normalized_url(value: str) -> str:
    """统一协议、主机、末尾斜线并移除片段，用于同址判定。"""
    parts = urlparse(value)
    path = parts.path.rstrip("/") or "/"
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{path}?{parts.query}".rstrip("?")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按右侧导航职务组和姓名链接原始顺序提取。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None or clean_compact(region.find("h3").get_text(" ", strip=True) if region.find("h3") else "") != "市政府领导":
        raise RuntimeError("未找到市政府领导右侧导航")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for group in region.select("ul > li"):
        duty_node = group.select_one(":scope > .sz-title")
        duty = clean_compact(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty.endswith("长"):
            continue
        for link in group.select(":scope > .sz-name-list a[href]"):
            name = clean_compact(link.get_text(" ", strip=True))
            href = clean_text(link.get("href"))
            detail_url = urljoin(base_url, href) if href else ""
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                continue
            if name in seen_names or urlparse(detail_url).scheme not in {"http", "https"}:
                continue
            if normalized_url(detail_url) in {
                normalized_url(page_rule["url"]),
                normalized_url(base_url),
            }:
                detail_url = ""
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": detail_url,
                    "confidence": "high",
                    "parser": page_rule["parser"],
                    "selector_summary": ".sz-nav市政府领导职务组与.sz-name-list姓名链接",
                }
            )

    if not rows:
        raise RuntimeError("市政府领导右侧导航未提取到有效人物")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
