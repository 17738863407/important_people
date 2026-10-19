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


PAGE_RULE = {
    "rule_id": "3391",
    "domain": "zjw.sh.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "shanghai_housing_committee_ld_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_ld_detail_shanghai_housing_committee_leader_v2",
    "leader_region_selector": ".ld-detail",
    "name_pattern": r"机构领导\s+(.+?)\s+[男女]，",
    "current_duty_pattern": r"(现任[^。]*。)",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "姓名与现任职务位于同一简介块；仅限当前.ld-detail节点内匹配",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按页面中的领导简介块顺序提取姓名与完整“现任……”原句。"""
    from bs4 import BeautifulSoup

    del final_url
    soup = BeautifulSoup(html, "html.parser")
    name_pattern = re.compile(str(page_rule["name_pattern"]))
    duty_pattern = re.compile(str(page_rule["current_duty_pattern"]))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for node in soup.select(str(page_rule["leader_region_selector"])):
        text = re.sub(r"[\s\u00a0\u3000]+", " ", node.get_text(" ", strip=True)).strip()
        name_match = name_pattern.search(text)
        duty_match = duty_pattern.search(text)
        if not name_match or not duty_match:
            continue

        name = re.sub(r"\s+", "", name_match.group(1))
        evidence = re.sub(
            r"^现任(?:职务)?\s*[：:]?\s*",
            "",
            re.sub(r"[\s\u00a0\u3000]+", "", duty_match.group(1)),
        )
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name):
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule["parser"]),
                "selector_summary": ".ld-detail内姓名与完整现任句",
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
