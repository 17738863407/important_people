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
    "rule_id": "2190",
    "page_type": "现任领导信息页",
    "structure_group": "正文列表职务姓名冒号字段",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofPersonnelLeaderColonListParser_v2",
    "leader_region_selector": ".conabout .TRS_Editor li, .conabout .TRS_Editor p",
    "risk_flag": "首条人物存在嵌套li和p重复DOM，须按姓名去重；职务不得补写机构前缀",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """将姓名字距和字段排版空白归一。"""
    return re.sub(r"[\s\u00a0\u3000]+", " ", str(value or "")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按正文DOM顺序解析冒号职务姓名字段并去除嵌套重复。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for node in soup.select(rule["leader_region_selector"]):
        text = _clean_text(node.get_text(" ", strip=True))
        parts = re.split(r"[：:]", text, maxsplit=1)
        if len(parts) != 2:
            continue
        duty = _clean_text(parts[0])
        name = re.sub(r"\s+", "", _clean_text(parts[1]))
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": ".conabout .TRS_Editor冒号字段；姓名去重",
            }
        )
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
