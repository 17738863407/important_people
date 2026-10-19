from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3922",
    "page_type": "机关简介内领导分组",
    "structure_group": "zunyi_government_grouped_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_zunyi_government_groups_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".zfxxgk_zdgkc dl（含市政府领导）",
    "name_selector": "dt/dd直属a[title]",
    "duty_selector": "dt/dd直属.stitle",
    "detail_link_selector": "dt/dd直属a[href]",
    "risk_flag": "同类容器后接市政府工作机构；仅接受含人物title链接的首个dl",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按dt/dd职务组及人物链接顺序提取。"""
    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    region = next(
        (
            block
            for block in soup.select(".zfxxgk_zdgkc dl")
            if block.select_one(":scope > dt a[href][title]") is not None
        ),
        None,
    )
    if region is None:
        raise RuntimeError("未定位到市政府领导分组")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for group in region.find_all(["dt", "dd"], recursive=False):
        duty_node = group.find("div", class_="stitle", recursive=False)
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty:
            continue
        for link in group.find_all("a", href=True, title=True, recursive=False):
            name = clean_name(link.get("title") or link.get_text(" ", strip=True))
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
                    "selector_summary": "领导dl直属dt/dd职务组及直属人物链接",
                }
            )

    if not rows:
        raise RuntimeError("市政府领导分组未提取到有效人物")
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
