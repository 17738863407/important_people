from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "3918",
    "page_type": "混合标签职务分组卡片",
    "structure_group": "zhongwei_government_mixed_group_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_zhongwei_government_groups_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "ul.leaderlist",
    "name_selector": "直属li a p",
    "duty_selector": "市长卡片前缀及直属div职务标题",
    "detail_link_selector": "直属li a[href]",
    "risk_flag": "无效HTML在ul内混排div职务标题；必须按直属节点顺序维护当前职务",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按ul直属节点顺序继承职务标题并提取人物。"""
    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    region = soup.select_one("ul.leaderlist")
    if region is None:
        raise RuntimeError("未定位到政府领导卡片列表")

    rows: list[dict] = []
    seen_names: set[str] = set()
    current_duty = ""
    for child in region.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "div":
            label = clean_text(child.get_text(" ", strip=True))
            if label in {"副市长", "秘书长"}:
                current_duty = label
            continue
        if child.name != "li":
            continue
        link = child.find("a", href=True, recursive=False)
        name_node = link.find("p") if link else None
        label = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        parts = re.split(r"[：:]", label, maxsplit=1)
        if len(parts) == 2:
            duty = clean_text(parts[0])
            name = clean_name(parts[1])
        else:
            duty = current_duty
            name = clean_name(label)
        href = clean_text(link.get("href")) if link else ""
        detail_url = urljoin(base_url, href) if href else ""
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            continue
        if name in seen_names or urlparse(detail_url).scheme not in {"http", "https"}:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "ul.leaderlist直属li与div职务标题顺序",
            }
        )

    if not rows:
        raise RuntimeError("政府领导卡片列表未提取到有效人物")
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
