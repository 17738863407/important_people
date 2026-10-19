from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1853",
    "page_type": "人物表格页",
    "structure_group": "ndsc_leader_dash_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "builtin_parse_page",
    "leader_region_selector": "div#content > div[style*='padding']",
    "name_selector": "p中破折号前文本",
    "duty_selector": "p中破折号后文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "普通HTTP返回403防护页，正文需浏览器渲染",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """清理网页排版空白。"""
    value = re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()
    value = re.sub(r"([（(])\s+", r"\1", value)
    return re.sub(r"\s+([）)])", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按中心领导正文中的姓名破折号职务段落顺序提取。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    for paragraph in soup.select("div#content > div[style*='padding'] > p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,5})\s*[—-]\s*(?P<duty>.+)", text)
        if match is None:
            continue
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=match.group("name"),
                duty=_clean_text(match.group("duty")),
                detail_url="",
                evidence=_clean_text(match.group("duty")),
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="content正文姓名破折号职务段落",
            )
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
