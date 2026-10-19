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
    "rule_id": "3290",
    "page_type": "职务分组名单页",
    "structure_group": "TRS正文职务冒号姓名",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofAssetAppraisalLeaderGroupParser_v2",
    "leader_region_selector": ".listBox .TRS_Editor",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文仅有职务冒号姓名，无独立人物详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按正文段落顺序抽取职务与姓名，完整段落作为原文证据。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".listBox .TRS_Editor")
    if region is None:
        raise RuntimeError("未找到领导简介正文 .listBox .TRS_Editor")

    rows: list[dict] = []
    for paragraph in region.select("p"):
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>[^：:]+?)\s*[：:]\s*(?P<names>.+)", evidence)
        if not match:
            continue
        duty = _clean_text(match.group("duty"))
        names = [re.sub(r"\s+", "", item) for item in re.split(r"[、，,]", match.group("names"))]
        for name in names:
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "parser": PAGE_RULE["parser"],
                    "selector_summary": ".listBox .TRS_Editor p",
                }
            )

    if not rows:
        raise RuntimeError("领导简介正文未解析到职务冒号姓名")
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
