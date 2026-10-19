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


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def clean_name(value: str) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " "))


def parse_page(
    html: str,
    _final_url: str,
    _page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """解析“姓名（职务）：工作分工”段落，仅保留括号内职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".xxgk-xl-text .view")
    if region is None:
        raise ValueError("未找到领导信息正文 .xxgk-xl-text .view")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.xxgk-xl-text .view；"
        "row=直接子p且开头为姓名（职务）：；"
        "name=左括号前文本；duty=括号内职务；detail=none"
    )
    for paragraph in region.find_all("p", recursive=False):
        paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
        heading_match = re.match(
            r"^([\u4e00-\u9fff·\s]{2,12})\s*[（(]\s*([^）)]+?)\s*[）)]\s*[:：]",
            paragraph_text,
        )
        if heading_match is None:
            continue
        name = clean_name(heading_match.group(1))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if name in seen_names:
            raise ValueError(f"领导信息正文出现重复姓名：{name}")
        seen_names.add(name)
        evidence = clean_text(heading_match.group(2))
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_yinchuan_investment_heading_v2",
                "selector_summary": selector_summary,
            }
        )

    if not rows:
        raise ValueError("领导信息正文未解析出有效的姓名（职务）标题")
    return rows


PAGE_RULE = {
    "rule_id": "3179",
    "page_type": "多人物详情合并页",
    "structure_group": "yinchuan_investment_heading_current",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "article_heading_blocks",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_investment_heading_v2",
    "leader_region_selector": ".xxgk-xl-text .view",
    "name_selector": ".xxgk-xl-text .view > p[文本结构=姓名（职务）：]左括号前文本",
    "duty_selector": ".xxgk-xl-text .view > p[文本结构=姓名（职务）：]括号内文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "每个领导标题后紧跟长篇工作分工；仅解析标题括号内职务，职责段全部排除",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".xxgk-xl-text .view",
            "name_selector": ".xxgk-xl-text .view > p[文本结构=姓名（职务）：]左括号前文本",
            "duty_selector": ".xxgk-xl-text .view > p[文本结构=姓名（职务）：]括号内文本",
            "detail_link_selector": "",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态正文的人物标题稳定提供姓名和括号内职务",
        },
        "migration": {
            "source": "failed_script_v3_task7",
            "verified_status": "online_verified_20260823",
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
