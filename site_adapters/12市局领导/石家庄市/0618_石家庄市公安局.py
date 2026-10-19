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
    "rule_id": "0618", "page_type": "人物列表完整页", "structure_group": "sjz_police_spaced_name_lines_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_police_spaced_name_lines_v2",
    "leader_region_selector": "div#conN", "name_selector": "直接子div开头2至4个中文姓名字符",
    "duty_selector": "姓名字段后原文", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "二字姓名内部含排版空白，姓名清理不得改变职务标点",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文直接子div顺序解析允许内部排版空白的姓名字段。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("div#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    records: list[object] = []
    seen_names: set[str] = set()
    pattern = re.compile(r"^(?P<name>[\u3400-\u9fff·](?:\s*[\u3400-\u9fff·]){1,3})\s+(?P<duty>.+)$")
    for node in regions[0].find_all("div", recursive=False):
        raw_text = node.get_text(" ", strip=True).replace("\u3000", " ").replace("\xa0", " ")
        text = re.sub(r"\s+", " ", raw_text).strip()
        match = pattern.fullmatch(text)
        if match is None:
            raise RuntimeError(f"领导行缺少姓名职务结构：{text}")
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = clean_text(match.group("duty"))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or not evidence or name in seen_names:
            raise RuntimeError(f"领导行姓名、职务异常或姓名重复：{name}")
        if node.select_one("a[href]") is not None:
            raise RuntimeError(f"领导行出现未审计链接：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("领导正文没有有效人物行")
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
