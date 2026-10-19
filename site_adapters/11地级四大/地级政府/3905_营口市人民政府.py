from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3905",
    "page_type": "领导职务分组链接列表",
    "structure_group": "yingkou_government_grouped_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "grouped_links",
    "collector": "requests",
    "parser": "page_inline_yingkou_government_groups_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".ewb-info-list",
    "name_selector": ".ewb-info-name a[href]",
    "duty_selector": ".ewb-info-tt",
    "detail_link_selector": ".ewb-info-name a[href]",
    "risk_flag": "页面存在注释中的空秘书长模板及后续领导活动；须只解析可见职务分组节点",
    "confidence": "high",
    "filter_policy": "strict_structure",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def clean_duty(value: object) -> str:
    """删除明确职务标签末尾冒号。"""
    return re.sub(r"[：:]$", "", clean_text(value)).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按可见职务分组与人物链接的页面顺序提取。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到市政府领导分组列表")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for group in region.select(":scope > .ewb-info-node"):
        label = group.select_one(":scope > .ewb-info-tt")
        duty = clean_duty(label.get_text(" ", strip=True) if label else "")
        if not duty.endswith("长"):
            continue
        for link in group.select(":scope > .ewb-info-name a[href]"):
            name = clean_name(link.get_text(" ", strip=True))
            href = clean_text(link.get("href"))
            detail_url = urljoin(base_url, href) if href else ""
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
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
                    "selector_summary": ".ewb-info-node职务标签与.ewb-info-name人物链接",
                }
            )

    if not rows:
        raise RuntimeError("市政府领导分组列表未提取到有效人物")
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
