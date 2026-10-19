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
    "rule_id": "0231",
    "domain": "www.chinawestagr.com",
    "page_type": "职务分组名单页",
    "structure_group": "chinawestagr_duty_colon_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_chinawestagr_duty_colon_list_v2",
    "leader_region_selector": "div.chaysfl_bot li",
    "row_link_selector": "a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "list_item_link",
    },
    "risk_flag": "入口页同时是首位人物详情页；等于依据链接的链接必须留空",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性清理项目符号和排版空白。"""
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", "")).strip(" ·")


def is_name_text(value: str) -> bool:
    """校验冒号后的文本是否为简短中文姓名。"""
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_text(value)))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按左侧领导名单的页面顺序解析“职务：姓名”条目。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule["url"]).strip()
    rows: list[dict[str, str]] = []

    for item in soup.select(str(page_rule["leader_region_selector"])):
        link = item.select_one(str(page_rule["row_link_selector"]))
        text = clean_text(link.get_text(" ", strip=True) if link else item.get_text(" ", strip=True))
        if "：" not in text:
            continue

        duty, name = (clean_text(part) for part in text.split("：", 1))
        if not duty or not is_name_text(name):
            continue

        href = str(link.get("href") or "").strip() if link else ""
        detail_url = urljoin(final_url or source_url, href) if href else ""
        if detail_url in {source_url, final_url}:
            detail_url = ""

        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule["parser"]),
                "selector_summary": "div.chaysfl_bot li内职务：姓名及人物链接",
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
