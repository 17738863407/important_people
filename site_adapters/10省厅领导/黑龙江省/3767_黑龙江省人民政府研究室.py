from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3767",
    "domain": "www.hlj.gov.cn",
    "page_type": "机构简介中的领导班子段落",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_hlj_research_office_v1",
    "leader_region_selector": ".detailContent",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "二、领导班子成员", "end_anchor": "三、内设机构", "include_selectors": [], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "需严格限制在领导班子与内设机构标题之间",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理页面排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析领导班子标题后的逐人段落，并在下一节标题处停止。"""
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.select(".detailContent p")
    in_scope = False
    rows: list[dict[str, str]] = []
    for paragraph in paragraphs:
        text = clean_text(paragraph.get_text(" ", strip=True))
        if "领导班子成员" in text:
            in_scope = True
            continue
        if in_scope and ("内设机构" in text or re.match(r"^三[、.]", text)):
            break
        if not in_scope:
            continue
        match = re.fullmatch(r"([\u4e00-\u9fff·\s]{2,8})\s*[男女]\s*(.+)", text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        duty = clean_text(match.group(2))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": "",
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
        })
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
