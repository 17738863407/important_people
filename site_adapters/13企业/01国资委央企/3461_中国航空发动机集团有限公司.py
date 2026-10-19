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
    "rule_id": "3461",
    "page_type": "职务分组名单页",
    "structure_group": "中国航发领导职务冒号姓名段落",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "AeccDutyColonNameParagraphParser_v1",
    "leader_region_selector": ".plr1.zoom.ysfcList > p",
    "name_selector": "段落冒号后",
    "duty_selector": "段落冒号前",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名含全角排版空格；仅作确定性空白清理",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _display_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导区域段落顺序解析职务和姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in soup.select(".plr1.zoom.ysfcList > p"):
        evidence = _display_text(paragraph.get_text(" ", strip=True))
        parts = re.split(r"[：:]", evidence, maxsplit=1)
        if len(parts) != 2:
            continue
        duty = parts[0].strip()
        name = re.sub(r"\s+", "", parts[1])
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
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
                "selector_summary": ".plr1.zoom.ysfcList > p；冒号前职务、冒号后姓名",
            }
        )
    if not records:
        raise RuntimeError("中国航发领导区域未解析到人物记录")
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
