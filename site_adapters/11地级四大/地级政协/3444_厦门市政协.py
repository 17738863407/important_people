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
    "rule_id": "3444",
    "page_type": "职务分组名单页",
    "structure_group": "冒号标题与后续姓名段落",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "XiamenCppccParagraphGroupParser_v2",
    "leader_region_selector": ".TRS_Editor p",
    "risk_flag": "分组职务标题仅在首段出现，后续姓名段落继承至下一冒号标题",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一正文排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(value: str) -> str:
    """姓名字段仅去除排版空白。"""
    return "".join(_clean_text(value).split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按正文段落顺序维护当前职务分组并解析姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    current_duty = ""
    for paragraph in soup.select(rule["leader_region_selector"]):
        text = _clean_text(paragraph.get_text(" ", strip=True)).replace(":", "：")
        if not text:
            continue
        name_text = text
        if "：" in text:
            duty_text, name_text = text.split("：", 1)
            current_duty = _clean_text(duty_text)
        name = _clean_name(name_text)
        if not current_duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": current_duty,
                "evidence": current_duty,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": ".TRS_Editor人物段落；冒号前职务组供后续姓名继承",
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
