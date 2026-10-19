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
    "rule_id": "4332",
    "page_type": "特派员简历入口页",
    "structure_group": "ocmfa_hk_commissioner_name_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_ocmfa_hk_commissioner_v1",
    "leader_region_selector": ".text-center .name",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口页仅展示姓名与特派员职务，人物详情链接未在当前姓名节点提供。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "explicit_css_plus_regex",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从特派员姓名节点提取姓名，并由同一节点中的职务后缀形成证据。"""
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one(".text-center .name")
    text = " ".join(node.get_text(" ", strip=True).split()) if node else ""
    matched = re.fullmatch(r"([\u3400-\u9fff·]{2,8})(特派员)", text)
    if not matched:
        raise RuntimeError("未在特派员简历页定位到‘姓名+特派员’结构")
    return [{"name": matched.group(1), "duty": matched.group(2), "detail_url": ""}]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
