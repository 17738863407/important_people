from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3877",
    "page_type": "人物目录详情页",
    "structure_group": "sanming_government_sidebar_leaders_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_sanming_government_sidebar_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "ul.ld_list",
    "name_selector": "li a[href]",
    "duty_selector": "li a[href] > i",
    "detail_link_selector": "li a[href]",
    "risk_flag": "同页含简历、分工和活动报道，仅解析左侧完整领导目录",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩排版空白，不改变职务字段语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def normalized_url(value: str) -> str:
    """移除片段并统一末尾斜线，用于入口与详情链接比较。"""
    parts = urlsplit(value)
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{parts.path.rstrip('/')}"


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按左侧领导目录的原始顺序提取姓名、职务及详情链接。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到市政府领导目录")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for item in region.select("li"):
        link = item.select_one("a[href]")
        duty_node = link.select_one("i") if link else None
        if link is None or duty_node is None:
            continue
        duty = clean_text(duty_node.get_text(" ", strip=True))
        duty_node.extract()
        name = clean_name(link.get_text(" ", strip=True))
        href = clean_text(link.get("href"))
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not duty:
            continue
        if name in seen_names:
            continue
        if detail_url and normalized_url(detail_url) == normalized_url(page_rule["url"]):
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
                "selector_summary": "ul.ld_list li a[href]姓名文本 + 子节点i职务标签",
            }
        )

    if not rows:
        raise RuntimeError("市政府领导目录未提取到有效人物")
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
