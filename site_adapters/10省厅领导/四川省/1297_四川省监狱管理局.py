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
    "rule_id": "1297",
    "domain": "jyglj.sc.gov.cn",
    "page_type": "人物表格页",
    "structure_group": "sichuan_prison_leader_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_sichuan_prison_leader_list_v2",
    "leader_region_selector": "div.leader-list li",
    "name_selector": ".l-l h3",
    "duty_selector": ".l-r dl:first-of-type dd",
    "detail_link_selector": ".more a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "list_item_link",
    },
    "risk_flag": "人物卡片还含主管工作和个人简历；只读取姓名节点与首个职务dd",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(value: str) -> str:
    """压缩连续空白和全角空格。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ")).strip()


def clean_name(value: str) -> str:
    """清理姓名节点中的冒号和排版空白。"""
    return normalize_space(value).replace("：", "").replace(":", "").replace(" ", "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片DOM顺序提取姓名、原始职务和独立人物页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url or str(page_rule["url"])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(str(page_rule["leader_region_selector"])):
        name_node = item.select_one(str(page_rule["name_selector"]))
        duty_node = item.select_one(str(page_rule["duty_selector"]))
        link = item.select_one(str(page_rule["detail_link_selector"]))
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = normalize_space(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty or name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue

        href = str(link.get("href") or "").strip() if link else ""
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
                "selector_summary": "div.leader-list li内h3姓名、首个dl dd职务及more链接",
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
