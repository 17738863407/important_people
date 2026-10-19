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
    "rule_id": "1524",
    "page_type": "人物列表完整页",
    "structure_group": "文旅部机关正文首部混合领导节点",
    "reuse_scope": "mct_department_article",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MctDepartmentArticleMixedLeadersParser_v2",
    "leader_region_selector": "#zoom .TRS_Editor",
    "name_selector": "主要职责标题前直属p/div冒号后",
    "duty_selector": "主要职责标题前直属p/div冒号前",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导记录混用p和div，正文后续含主要职责及内设机构；必须按直属节点顺序并在主要职责处停止。页面iframe仅为页脚",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析正文首部混合p/div节点中的“职务：姓名”记录。"""
    soup = BeautifulSoup(html, "html.parser")
    editor = soup.select_one("#zoom .TRS_Editor")
    if editor is None:
        raise RuntimeError("未找到资源开发司正文#zoom .TRS_Editor")
    records: list[dict] = []
    seen_names: set[str] = set()
    for node in editor.find_all(["p", "div"], recursive=False):
        evidence = _clean_text(node.get_text(" ", strip=True))
        if evidence.startswith("主要职责"):
            break
        matched = re.fullmatch(r"(.+?)[：:]([\u4e00-\u9fff·]{2,5})", evidence)
        if not matched:
            continue
        duty, name = matched.groups()
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "#zoom .TRS_Editor直属p/div；主要职责标题前；职务：姓名完整原文",
            }
        )
    if not records:
        raise RuntimeError("资源开发司正文首部未解析到领导记录")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
