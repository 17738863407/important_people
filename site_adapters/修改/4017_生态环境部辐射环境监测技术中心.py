from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4017",
    "page_type": "机构归属待复核页",
    "structure_group": "organization_identity_guard_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_organization_identity_guard_v1",
    "risk_flag": "规则主表入口页当前展示的机构与目标机构不一致，禁止误采其他机构领导。",
    "confidence": "high",
    "profile_reusable": False,
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """校验页面机构归属，不把错误入口页的人物误归入目标机构。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    organization = str(page_rule.get("organization") or "").strip()
    if organization and organization not in page_text:
        title = soup.title.get_text(" ", strip=True) if soup.title else "无标题"
        raise RuntimeError(
            f"入口页机构归属不一致：目标机构为{organization}，当前页面标题为{title}"
        )
    raise RuntimeError("入口页未发现可验证的目标机构领导结构")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
