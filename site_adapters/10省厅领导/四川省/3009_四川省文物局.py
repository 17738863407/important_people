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
    "rule_id": "3009",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_heritage_labeled_leaders",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_sichuan_heritage_labeled_leaders_v1",
    "leader_region_selector": ".szfbgtdiv .list",
    "name_selector": ".lader p lable",
    "duty_selector": ".lader p lable",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导简介",
        "end_anchor": "机构设置",
        "include_selectors": [".szfbgtdiv .list"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "同页含主要职责、机构设置、直属单位及主管事务；仅使用姓名/职位标签",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".szfbgtdiv .list",
            "name_selector": ".lader p lable",
            "duty_selector": ".lader p lable",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "领导简介",
                "end_anchor": "机构设置",
                "include_selectors": [".szfbgtdiv .list"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML领导简介块直接包含姓名和职位标签，无人物详情链接",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理页面排版空白，不改变职位文字。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析领导简介块的姓名、职位标签，继承页面DOM顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for block in soup.select(".szfbgtdiv .list .lader"):
        fields: dict[str, str] = {}
        for paragraph in block.find_all("p", recursive=False):
            label_node = paragraph.find("lable")
            value_node = paragraph.find("span")
            if not label_node or not value_node:
                continue
            label = _clean_text(label_node.get_text(" ", strip=True)).rstrip("：:")
            value = _clean_text(value_node.get_text(" ", strip=True))
            if label in {"姓名", "职位"}:
                fields[label] = value

        name = re.sub(r"\s+", "", fields.get("姓名", ""))
        duty = fields.get("职位", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_sichuan_heritage_labeled_leaders_v1",
                "selector_summary": ".szfbgtdiv .list .lader；姓名/职位lable对应span",
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
