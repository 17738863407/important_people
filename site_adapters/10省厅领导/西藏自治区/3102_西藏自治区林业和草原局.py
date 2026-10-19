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
    "rule_id": "3102",
    "page_type": "人物列表完整页",
    "structure_group": "xizang_forestry_dt_duty_dd_name",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_xizang_forestry_dt_duty_dd_name_v1",
    "leader_region_selector": "dl.leaders#lingdao",
    "name_selector": "dl.leaders#lingdao dt + dd",
    "duty_selector": "dl.leaders#lingdao dt",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导专区首个有效dt",
        "end_anchor": "最后一个有效dd",
        "include_selectors": ["dl.leaders#lingdao"],
        "exclude_selectors": ["空dt/dd占位"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "首页专区尾部含空dt/dd占位；只接受非空职务及合法姓名，不给职务添加机构前缀",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "dl.leaders#lingdao",
            "name_selector": "dt + dd",
            "duty_selector": "dt",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "首个有效dt",
                "end_anchor": "末个有效dd",
                "include_selectors": ["dl.leaders#lingdao dt", "dl.leaders#lingdao dd"],
                "exclude_selectors": ["空节点"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML首页专区直接提供职务和姓名配对",
        },
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return " ".join(text.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按首页领导专区DOM顺序配对dt原始职务和相邻dd姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one("dl.leaders#lingdao")
    if box is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for duty_node in box.select("dt"):
        name_node = duty_node.find_next_sibling("dd")
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_xizang_forestry_dt_duty_dd_name_v1",
                "selector_summary": "dl.leaders#lingdao；dt职务/dd姓名配对",
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
