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
    "rule_id": "0330",
    "page_type": "人物表格页",
    "structure_group": "编辑器领导段落",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CrsmotLeaderParagraphParser_v2",
    "leader_region_selector": "div.view.TRS_UEDITOR p",
    "name_selector": "机构名前文本",
    "duty_selector": "完整段落原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面响应需正确识别UTF-8编码；姓名含全角及特殊排版空格，且入口页不是人物详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2002-\u200a\u202f\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按编辑器段落DOM顺序抽取机构名前姓名及完整段落证据。"""
    soup = BeautifulSoup(html, "lxml")
    organization_marker = "交通运输部救助打捞局"
    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in soup.select("div.view.TRS_UEDITOR p"):
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        if organization_marker not in evidence:
            continue
        name_part, duty_part = evidence.split(organization_marker, 1)
        name = re.sub(r"\s+", "", name_part)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not _clean_text(duty_part) or name in seen_names:
            continue
        seen_names.add(name)
        raw_duty = f"{organization_marker}{_clean_text(duty_part)}"
        records.append(
            {
                "name": name,
                "duty": raw_duty,
                "evidence": raw_duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "div.view.TRS_UEDITOR p；机构名前姓名；完整段落证据",
            }
        )
    if not records:
        raise RuntimeError("领导编辑器段落未解析到人物记录")
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
