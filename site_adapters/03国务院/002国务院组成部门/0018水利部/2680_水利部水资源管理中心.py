from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


PAGE_RULE: dict[str, Any] = {
    "rule_id": "2680",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".tabcontent",
    "parser_id": "custom_szyzx_people_composition_v1",
    "structure_group": "人员组成标签页_职务标题加简介段落",
    "confidence": "high",
    "risk_notes": "仅接受以冒号结尾的职务标题及其同容器直属简介段落，HTML注释中的历史人物不会进入DOM元素遍历。",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, Any]) -> list[dict[str, str]]:
    """解析“人员组成”区域中按页面顺序排列的职务标题和人物简介。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(page_rule["leader_region_selector"])
    if scope is None:
        raise RuntimeError("未找到人员组成标签页容器")

    rows: list[dict[str, str]] = []
    for title_node in scope.select("strong"):
        raw_title = _clean_text(title_node.get_text(" ", strip=True))
        if not raw_title.endswith((":", "：")):
            continue

        container = title_node.parent
        profile_node = container.find("p", recursive=False) if container is not None else None
        if profile_node is None:
            continue

        profile = _clean_text(profile_node.get_text(" ", strip=True))
        name_match = re.match(r"^([\u3400-\u9fff·]{2,20})[，,]", profile)
        if name_match is None:
            continue

        rows.append(
            {
                "name": name_match.group(1),
                "duty": raw_title.rstrip(":：").strip(),
                "detail_url": "",
            }
        )

    if not rows:
        raise RuntimeError("人员组成区域未解析到有效人物记录")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
