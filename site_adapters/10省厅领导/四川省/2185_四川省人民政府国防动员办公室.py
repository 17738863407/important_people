from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2185",
    "domain": "rfb.sc.gov.cn",
    "page_type": "人物表格页",
    "structure_group": "sichuan_defense_mobilization_leader_dl",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_sichuan_defense_mobilization_leader_dl_v1",
    "leader_region_selector": "#news_list > dl.clearfix",
    "name_link_selector": "dt.pad_t10 .ft2 a[href]",
    "duty_label": "职务：",
    "detail_strategy": {
        "required": False,
        "mode": "name_link",
    },
    "risk_flag": "页面含左侧姓名目录、注释简历和未渲染模板占位符；只解析#news_list直属人物dl",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(value: str) -> str:
    """压缩页面字段中的连续空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物dl顺序提取姓名、明确职务字段和独立人物页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url or str(page_rule["url"])
    duty_label = str(page_rule["duty_label"])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(str(page_rule["leader_region_selector"])):
        name_link = item.select_one(str(page_rule["name_link_selector"]))
        if name_link is None:
            continue
        name = re.sub(r"\s+", "", name_link.get_text(" ", strip=True))

        duty = ""
        for field in item.find_all("dt", recursive=False):
            text = normalize_space(field.get_text(" ", strip=True))
            if text.startswith(duty_label):
                duty = text[len(duty_label):].strip()
                break
        if not duty or name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue

        href = str(name_link.get("href") or "").strip()
        detail_url = urljoin(source_url, href) if href else ""
        if detail_url in {source_url, str(page_rule["url"])}:
            detail_url = ""

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule["parser"]),
                "selector_summary": "#news_list直属人物dl中的姓名链接和职务dt字段",
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
