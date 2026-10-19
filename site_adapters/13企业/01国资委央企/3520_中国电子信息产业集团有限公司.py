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
    "rule_id": "3520",
    "page_type": "人物列表完整页",
    "structure_group": "中国电子集团领导图文卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CecLeaderCardParser_v2",
    "leader_region_selector": ".cc-row.hvr-underline-from-left",
    "name_selector": ".cc-textblock__body.richtext p",
    "duty_selector": ".cc-textblock__body.richtext p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面构建器类名较多；以9张领导卡片及非空段落的姓名、职务顺序定位",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导图文卡片顺序读取前两个非空段落作为姓名与职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select(".cc-row.hvr-underline-from-left"):
        paragraphs = [
            text
            for node in card.select(".cc-textblock__body.richtext p")
            if (text := _clean_text(node.get_text(" ", strip=True)))
        ]
        if len(paragraphs) < 2:
            continue
        name = re.sub(r"\s+", "", paragraphs[0])
        evidence = paragraphs[1]
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
                "selector_summary": "hvr-underline卡片；前两个非空富文本p为姓名与职务",
            }
        )
    if not records:
        raise RuntimeError("中国电子集团领导图文卡片未解析到人物记录")
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
