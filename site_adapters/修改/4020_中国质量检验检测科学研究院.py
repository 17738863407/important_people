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
    "rule_id": "4020",
    "page_type": "院领导双列表格页",
    "structure_group": "caqit_leader_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML预期",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "online",
    "parser": "custom_caqit_leader_table_v1",
    "leader_region_selector": ".caiq_bygk_content table tr",
    "name_selector": "td.leader_name",
    "duty_selector": "td.leader_name + td",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "导航含重复名单且旧人员保存在HTML注释中，必须限定可见正文表格行",
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
    """按当前院领导正文表格顺序提取两列，不读取导航或注释名单。"""
    import re
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for tr in soup.select(".caiq_bygk_content table tr"):
        if any(node.has_attr("hidden") or node.get("aria-hidden") == "true" or "display:none" in str(node.get("style", "")).replace(" ", "") for node in [tr, *tr.parents]):
            continue
        name_node = tr.select_one("td.leader_name")
        duty_node = name_node.find_next_sibling("td") if name_node else None
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True)) if name_node else ""
        duty = re.sub(r"\s+", " ", duty_node.get_text(" ", strip=True)).strip() if duty_node else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not duty:
            continue
        if name in seen:
            raise RuntimeError("院领导正文表格出现重复姓名")
        seen.add(name)
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": str(page_rule["parser"])})
    if not rows:
        raise RuntimeError("院领导正文表格未取得可验证人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
