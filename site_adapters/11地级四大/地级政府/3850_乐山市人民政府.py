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


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从连续人物简介块中提取姓名及本人物块内的“现任”句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for name_node in soup.select(".text_field .ldxx_name"):
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        profile = name_node.find_next_sibling("div", class_="ldxx_jlCon")
        profile_text = clean_text(profile.get_text(" ", strip=True) if profile else "")
        current_match = re.search(r"现任([^。]+)", profile_text)
        duty = clean_text(current_match.group(1)) if current_match else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        rows.append({
            "name": name,
            "duty": "",
            "evidence": duty,
            "detail_url": "",
            "confidence": "high",
            "parser": "page_inline_leshan_government_profiles_v1",
        })
    return rows


PAGE_RULE = {
    "rule_id": "3850",
    "page_type": "单页连续领导简介",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "profile_blocks",
    "parser": "page_inline_leshan_government_profiles_v1",
    "leader_region_selector": ".text_field",
    "name_selector": ".ldxx_name",
    "duty_selector": ".ldxx_jlCon",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "页面无独立人物详情链接",
    "confidence": "high",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
