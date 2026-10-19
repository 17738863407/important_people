from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3878",
    "page_type": "职务分组人物卡片页",
    "structure_group": "sansha_government_grouped_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_sansha_government_groups_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".gkpd-ldd",
    "name_selector": "ul li a[href] em",
    "duty_selector": ":scope > span",
    "detail_link_selector": "ul li a[href]",
    "risk_flag": "页脚含大量外部机构链接，仅解析市政府领导职务分组",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白，不改变职务字段语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def is_same_entry(entry_url: str, detail_url: str) -> bool:
    """判断候选链接是否只是入口页本身。"""
    entry = urlsplit(entry_url)
    detail = urlsplit(detail_url)
    return (
        entry.scheme.lower(),
        entry.netloc.lower(),
        entry.path.rstrip("/"),
    ) == (
        detail.scheme.lower(),
        detail.netloc.lower(),
        detail.path.rstrip("/"),
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按职务分组和人物卡片原始顺序提取领导信息。"""
    soup = BeautifulSoup(html, "lxml")
    groups = soup.select(page_rule["leader_region_selector"])
    if not groups:
        raise RuntimeError("未找到市政府领导职务分组")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for group in groups:
        duty_node = group.find("span", recursive=False)
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty:
            continue
        for link in group.select("ul li a[href]"):
            name_node = link.select_one("em")
            name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
            href = clean_text(link.get("href"))
            detail_url = urljoin(base_url, href) if href else ""
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or name in seen_names:
                continue
            if not detail_url or is_same_entry(page_rule["url"], detail_url):
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
                    "selector_summary": ".gkpd-ldd直属span职务标题 + ul li a[href] em姓名",
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
