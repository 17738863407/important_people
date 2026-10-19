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


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按左侧市长、副市长分组及页面顺序提取人物。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for group in soup.select(".ldzc_l .ldzc_l2"):
        duty_node = group.select_one(".sx")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        for anchor in group.select(".xm2 a[href]"):
            name = clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
            if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            rows.append({
                "name": name,
                "duty": "",
                "evidence": duty,
                "detail_url": urljoin(source, str(anchor.get("href") or "")),
                "confidence": "high",
                "parser": "page_inline_jinzhou_government_groups_v1",
            })
    return rows


PAGE_RULE = {
    "rule_id": "3845",
    "page_type": "领导分组列表",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "grouped_list",
    "parser": "page_inline_jinzhou_government_groups_v1",
    "leader_region_selector": ".ldzc_l",
    "name_selector": ".ldzc_l2 .xm2 a",
    "duty_selector": ".ldzc_l2 .sx",
    "detail_link_selector": ".ldzc_l2 .xm2 a[href]",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "",
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
