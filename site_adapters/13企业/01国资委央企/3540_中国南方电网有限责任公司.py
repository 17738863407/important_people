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
    "rule_id": "3540",
    "page_type": "人物列表完整页",
    "structure_group": "南方电网公司领导图文条目",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "requests",
    "parser": "CsgLeaderListParser_v1",
    "leader_region_selector": "font.fB",
    "name_selector": "font.fB",
    "duty_selector": "font.fB所在li的其余文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "源HTML含不规范br嵌套且个别长职务排版换行，需从姓名节点回溯li并仅合并空白",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """从姓名font节点回溯人物条目，按DOM顺序提取完整职务文本。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for name_node in soup.select("font.fB"):
        card = name_node.find_parent("li")
        if card is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True))
        parts = [_clean_text(text) for text in card.get_text("\n", strip=True).splitlines()]
        parts = [part for part in parts if part and part != name]
        evidence = "".join(parts)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "fB姓名节点回溯最近li；移除姓名后合并排版换行得到职务",
            }
        )
    if not records:
        raise RuntimeError("南方电网公司领导条目未解析到人物记录")
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
