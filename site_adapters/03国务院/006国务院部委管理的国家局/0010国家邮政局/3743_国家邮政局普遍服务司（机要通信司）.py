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
    "rule_id": "3743", "page_type": "同页锚点机构职责", "structure_group": "spb_anchor_department_v1",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_inline_spb_anchor_department_v1", "leader_region_selector": "#pfs", "name_selector": "",
    "duty_selector": "", "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high", "filter_policy": "strong_no_wordlist", "risk_flag": "只解析pfs锚点标题父容器之后首个职责容器中的负责人字段，禁止跨入下一司局",
    "locator_strategy": "anchor_parent_next_div_responsible_field",
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    anchor = soup.find(id="pfs")
    scope = anchor.parent.find_next_sibling("div") if anchor is not None and anchor.parent is not None else None
    text = clean_text(scope.get_text(" ", strip=True)) if scope is not None else ""
    match = re.search(r"负责人[：:]\s*([\u4e00-\u9fff·]{2,8})\s+(.+)$", text)
    if match is None:
        return []
    name, duty = match.group(1), clean_text(match.group(2))
    return [{"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "scope=pfs_anchor_next_div；order=responsible_field"}]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
