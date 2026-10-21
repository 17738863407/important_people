from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2343",
    "page_type": "人物列表完整页",
    "structure_group": "hebei_gdb_empty_agency_profile_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "page_local_parse_page",
    "collector": "static_http",
    "parser": "page_local_parse_page",
    "leader_region_selector": ".deal .doll",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "risk_flag": "官网机构概况栏目当前为空，不能从任免或工作动态推断现任名单",
    "confidence": "low",
}


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """核验机构概况的业务列表；空列表时明确失败，不扫描导航或新闻。"""
    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    roster = soup.select_one(".deal .doll")
    if roster is None:
        raise ValueError("官网机构概况页缺少业务列表容器，无法核验现任领导")
    if not roster.find_all("li", recursive=False):
        raise ValueError("官网机构概况栏目当前为空，未提供可核验的现任领导名单")
    raise ValueError("官网机构概况栏目结构已变化，需重新在线核验后配置解析规则")


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
