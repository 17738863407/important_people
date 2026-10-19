from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0490",
    "page_type": "多人物详情合并页",
    "structure_group": "安徽省政府发展研究中心领导列表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_anhui_dss_title_split_v2",
    "leader_region_selector": ".listnews",
    "name_selector": "li a[title][href]标题末尾姓名",
    "duty_selector": "li a[title][href]标题前部职务",
    "detail_link_selector": "li a[title][href]",
    "risk_flag": "链接正文含工作分工和个人简介，仅解析title短标题",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩短标题排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按领导列表顺序拆分title中的职务与姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for link in soup.select(".listnews li a[title][href]"):
        title = clean_text(str(link.get("title") or ""))
        match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff·]{2,8})", title)
        if not match:
            continue
        duty, name = clean_text(match.group("duty")), match.group("name")
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_anhui_dss_title_split_v2",
                "selector_summary": "strategy=custom_parse_page；item=.listnews li a[title][href]；split=title末尾姓名",
            }
        )
    if not rows:
        raise RuntimeError("安徽省政府发展研究中心领导列表未抽取到人物")
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
