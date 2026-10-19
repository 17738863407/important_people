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
    "rule_id": "1234", "page_type": "人物列表完整页", "structure_group": "shenyang_transport_yangs_blocks_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_transport_yangs_blocks_v2",
    "leader_region_selector": "div.yangs", "name_selector": "人物块第一个直接子b",
    "duty_selector": "人物块第二个直接子b", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "文件历史标注动态DOM但当前原始HTML已直出；后续b为办公信息、p为工作分工，均须排除",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物块DOM顺序提取姓名和原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    blocks = soup.select("div.yangs")
    records: list[object] = []
    seen_names: set[str] = set()
    for block in blocks:
        bold_nodes = block.find_all("b", recursive=False)
        if len(bold_nodes) < 2:
            raise RuntimeError("人物块缺少姓名或职务直接子节点")
        name = re.sub(r"\s+", "", clean_text(bold_nodes[0].get_text(" ", strip=True)))
        evidence = clean_text(bold_nodes[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("人物块姓名或职务字段异常")
        if name in seen_names:
            raise RuntimeError(f"人物块姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("当前页面未提取到人物块")
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
