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
    "rule_id": "2846",
    "page_type": "职务分组名单页",
    "structure_group": "领导分组首行职务与续行姓名",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MiitEmergencyCenterDutyContinuationParser_v2",
    "leader_region_selector": "#title_2 + .word",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "副主任第二人位于无职务续行，需与上一职务行合并为完整分组证据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def _append_group(rows: list[dict], duty: str, names: list[str], evidence_parts: list[str]) -> None:
    if not duty or not names:
        return
    evidence = duty
    for name in names:
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "#title_2 + .word p；职务首行与姓名续行",
            }
        )


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导分组顺序抽取首行及姓名续行，并为组内人物保留完整证据。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#title_2 + .word")
    if region is None:
        raise RuntimeError("未找到领导名单区域 #title_2 + .word")

    rows: list[dict] = []
    current_duty = ""
    current_names: list[str] = []
    evidence_parts: list[str] = []
    for paragraph in region.select("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>主\s*任|副主任)\s*[：:]\s*(?P<names>.+)", text)
        if match:
            _append_group(rows, current_duty, current_names, evidence_parts)
            current_duty = _clean_text(match.group("duty"))
            current_names = [
                re.sub(r"\s+", "", name)
                for name in re.split(r"[、，,]", match.group("names"))
                if re.fullmatch(r"[\u4e00-\u9fff\s]{2,6}", name.strip())
            ]
            evidence_parts = [text]
            continue
        compact = re.sub(r"\s+", "", text)
        if current_duty and re.fullmatch(r"[\u4e00-\u9fff]{2,4}", compact):
            current_names.append(compact)
            evidence_parts.append(text)

    _append_group(rows, current_duty, current_names, evidence_parts)
    if not rows:
        raise RuntimeError("领导名单区域未解析到职务姓名分组")
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
