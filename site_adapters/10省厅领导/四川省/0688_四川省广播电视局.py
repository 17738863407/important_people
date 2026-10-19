from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0688",
    "domain": "gdj.sc.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_broadcast_intro_tab",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_sichuan_broadcast_intro_tab_v2",
    "tab_selector": ".scroll_cont.ScrollStyle.szfbgtdiv",
    "leader_tab_index": 1,
    "paragraph_selector": "p",
    "duty_boundary_pattern": r"\s+(?:主持|负责|完成|协助|分管)",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "同页含职责、内设机构和直属单位标签；仅解析第二个领导简介标签页中的段落首部",
    "confidence": "high",
    "filter_policy": "weak_allow_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\u00a0", " ").split())


def normalize_name(value: str) -> str:
    """移除姓名中的排版空格。"""
    return clean_text(value).replace(" ", "")


def split_name_duty(text: str, boundary_pattern: str) -> tuple[str, str]:
    """从当前领导段落开头切出姓名和原始职务。"""
    cleaned = clean_text(text)
    match = re.match(r"^([\u4e00-\u9fff]\s*[\u4e00-\u9fff]{1,3})\s+(.+)$", cleaned)
    if not match:
        return "", ""

    name = normalize_name(match.group(1))
    duty = re.split(boundary_pattern, match.group(2), maxsplit=1)[0]
    duty = clean_text(duty).replace("二级 巡视员", "二级巡视员")
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导简介标签页中的人物段落顺序提取姓名和职务。"""
    from bs4 import BeautifulSoup

    del final_url
    soup = BeautifulSoup(html, "html.parser")
    tabs = soup.select(str(page_rule["tab_selector"]))
    tab_index = int(page_rule["leader_tab_index"])
    if len(tabs) <= tab_index:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in tabs[tab_index].select(str(page_rule["paragraph_selector"])):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        name, duty = split_name_duty(text, str(page_rule["duty_boundary_pattern"]))
        if not duty or name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule["parser"]),
                "selector_summary": "第二个.scroll_cont.ScrollStyle.szfbgtdiv标签页内人物段落首部",
            }
        )

    return rows


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
