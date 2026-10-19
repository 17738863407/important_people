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


def clean_name(value: str) -> str:
    """删除姓名中的网页排版空白。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """从当前领导分工正文逐段提取明确姓名，不把分工内容冒充职务。"""
    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("#zoom.j-fontContent")
    if article is None:
        raise ValueError("未找到领导分工正文 #zoom.j-fontContent")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=#zoom.j-fontContent；"
        "name=直接p开头“姓名同志，”；duty/evidence=none（页面仅有主持、分管、负责等分工）"
    )
    name_pattern = re.compile(r"^(?P<name>[\u4e00-\u9fff·\s\u00a0]{2,12})同志\s*[，,]")
    for paragraph in article.select(":scope > p"):
        paragraph_text = " ".join(paragraph.get_text(" ", strip=True).split())
        match = name_pattern.match(paragraph_text)
        if match is None:
            continue
        name = clean_name(match.group("name"))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": "",
                "detail_url": "",
                "confidence": "medium",
                "parser": "page_inline_hefei_agriculture_name_only_v1",
                "selector_summary": selector_summary,
            }
        )

    if not rows:
        raise ValueError("领导分工正文未解析出“姓名同志”记录")
    return rows


PAGE_RULE = {
    "rule_id": "2035",
    "page_type": "领导信息正文页",
    "structure_group": "hefei_agriculture_duty_assignment_name_only",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "article_name_only",
    "collector": "browser_dom",
    "parser": "page_inline_hefei_agriculture_name_only_v1",
    "leader_region_selector": "#zoom.j-fontContent",
    "name_selector": ":scope > p",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文仅提供姓名和主持/分管/负责等分工，不提供可验证现任职务；按规则保留姓名并让依据说明为空",
    "confidence": "medium",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom.j-fontContent",
            "name_selector": ":scope > p",
            "duty_selector": "",
            "detail_link_selector": "",
        },
        "api": {
            "enabled": False,
            "reason": "当前公开正文已明确列出人物顺序，但没有职务字段或人物详情链接",
        },
        "migration": {
            "source": "failed_script_v3_task7",
            "verified_status": "online_verified_name_only_20260808",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
