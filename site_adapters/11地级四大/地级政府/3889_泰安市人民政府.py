from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3889",
    "page_type": "详情页内领导目录表格",
    "structure_group": "taian_government_leader_sidebar_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "grouped_links",
    "collector": "requests",
    "parser": "page_inline_taian_government_sidebar_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".xx_ldzy_h table.ldzy_li",
    "name_selector": "tr td a[href]",
    "duty_selector": "tr td:first-child",
    "detail_link_selector": "tr td a[href]",
    "risk_flag": "入口为首位领导详情；须限定市政府领导侧栏表格，排除正文简介、分工和市长信箱",
    "confidence": "high",
    "filter_policy": "strict_structure",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def clean_group_duty(value: object) -> str:
    """去除表格职务标题中的排版空白及末尾字段冒号。"""
    return re.sub(r"[：:]$", "", re.sub(r"\s+", "", clean_text(value))).strip()


def normalized_url(value: str) -> str:
    """统一协议、主机、末尾斜线并移除片段，用于同址判定。"""
    parts = urlparse(value)
    path = parts.path.rstrip("/") or "/"
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{path}?{parts.query}".rstrip("?")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按侧栏表格行和每行链接的原始顺序提取领导。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到市政府领导侧栏表格")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()

    def append_links(duty: str, container: object) -> None:
        """将一个明确职务单元格对应的人物链接依次加入结果。"""
        if not duty.endswith("长") or not hasattr(container, "select"):
            return
        for link in container.select("a[href]"):
            name = clean_name(link.get_text(" ", strip=True))
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
                    "selector_summary": ".xx_ldzy_h table.ldzy_li职务行及人物链接",
                }
            )

    pending_duty = ""
    for child in region.find_all(recursive=False):
        if child.name == "tr":
            cells = child.find_all("td", recursive=False)
            if len(cells) >= 2:
                append_links(clean_group_duty(cells[0].get_text(" ", strip=True)), cells[1])
            pending_duty = ""
            continue
        if child.name != "td":
            continue
        if child.select("a[href]"):
            append_links(pending_duty, child)
            pending_duty = ""
        else:
            pending_duty = clean_group_duty(child.get_text(" ", strip=True))

    if not rows:
        raise RuntimeError("市政府领导侧栏表格未提取到有效人物")
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
