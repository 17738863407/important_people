from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3902",
    "page_type": "市政府领导名录",
    "structure_group": "yangquan_government_leader_roster_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "requests",
    "parser": "page_inline_yangquan_government_leader_roster_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "ul.provincial-leaders-inner",
    "name_selector": "li dl > dd",
    "duty_selector": "li > .provincial-leaders-position",
    "detail_link_selector": "当前人物dl内a[href]",
    "risk_flag": "仅解析“市政府领导”栏目中职位标签与人物dl的对应关系，不扩展至政府组成部门",
    "confidence": "high",
    "filter_policy": "verified_current_sentence",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅保留姓名字符，剔除页面附注和排版空白。"""
    normalized = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()
    match = re.match(r"([\u3400-\u9fff·]{2,20})", normalized)
    return match.group(1) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按市政府领导栏目中职位标签与人物条目的原始顺序提取。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到市政府领导名录")

    rows: list[dict] = []
    base_url = final_url or page_rule["url"]
    for leader_group in region.find_all("li", recursive=False):
        position = clean_text(
            leader_group.select_one(".provincial-leaders-position").get_text(" ", strip=True)
            if leader_group.select_one(".provincial-leaders-position")
            else ""
        )
        if position not in {"市长", "副市长", "秘书长"}:
            continue
        for profile in leader_group.find_all("dl"):
            name_node = profile.find("dd", recursive=False)
            name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                continue
            link = profile.select_one("a[href]")
            href = clean_text(link.get("href")) if link else ""
            detail_url = urljoin(base_url, href) if href else ""
            if urlparse(detail_url).scheme not in {"http", "https"}:
                detail_url = ""
            rows.append(
                {
                    "name": name,
                    "duty": position,
                    "evidence": position,
                    "detail_url": detail_url,
                    "confidence": "high",
                    "parser": page_rule["parser"],
                    "selector_summary": "市政府领导栏目职位标签与同组人物dl",
                }
            )
    if not rows:
        raise RuntimeError("市政府领导名录未解析出有效人物")
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
