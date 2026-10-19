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
    "rule_id": "4266",
    "page_type": "领导信息卡片",
    "structure_group": "国家矿山安全监察局广东局领导卡片列表",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_chinamine_guangdong_leaders_v1",
    "leader_region_selector": "li:has(.title .job)",
    "name_selector": ".title .job + a[href]",
    "duty_selector": ".title .job",
    "detail_link_selector": ".title a[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "页面含站点导航和登录控件，必须以领导卡片的 `.title .job` 结构限定。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片 DOM 顺序解析职务、姓名和个人简介链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    base_url = final_url or str(page_rule["url"])
    for item in soup.select("li"):
        job = item.select_one(".title .job")
        link = item.select_one(".title a[href]")
        if job is None or link is None:
            continue
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", job.get_text(" ", strip=True)).rstrip("：:")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, link["href"]),
                "parser": page_rule["parser"],
                "selector_summary": "领导卡片 .title .job + 姓名简介链接",
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
