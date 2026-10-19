from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3883",
    "page_type": "人物目录详情页",
    "structure_group": "shuozhou_government_sidebar_leaders_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_inline_shuozhou_government_sidebar_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".ld-left",
    "name_selector": "ul li a[href] > .tn1",
    "duty_selector": "ul li a[href] > .tn2",
    "detail_link_selector": "ul li a[href]",
    "risk_flag": "普通HTTP返回403且页面含重复名单，仅解析渲染后.ld-left中的明确姓名职务字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_text(value: object) -> str:
    """删除姓名或短职务字段中的纯排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def same_page(reference_url: str, candidate_url: str) -> bool:
    """忽略查询和片段比较入口与候选详情路径。"""
    reference = urlsplit(reference_url)
    candidate = urlsplit(candidate_url)
    return (
        reference.scheme.lower(),
        reference.netloc.lower(),
        reference.path.rstrip("/"),
    ) == (
        candidate.scheme.lower(),
        candidate.netloc.lower(),
        candidate.path.rstrip("/"),
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按渲染侧栏原始顺序提取明确姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到领导详情页结构化侧栏")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for link in region.select("ul li a[href]"):
        name_node = link.select_one(":scope > .tn1")
        duty_node = link.select_one(":scope > .tn2")
        name = compact_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = compact_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not duty:
            continue
        if name in seen_names:
            continue
        if not detail_url or same_page(page_rule["url"], detail_url):
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
                "selector_summary": ".ld-left ul li a[href]直属.tn1姓名和.tn2职务",
            }
        )

    if not rows:
        raise RuntimeError("领导详情页结构化侧栏未提取到有效人物")
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
