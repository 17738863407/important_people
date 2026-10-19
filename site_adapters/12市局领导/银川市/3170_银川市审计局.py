from __future__ import annotations

import sys
from pathlib import Path
import re

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "3170",
    "page_type": "多人物详情合并页",
    "structure_group": "yinchuan_audit_strong_name_first_sentence",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "yinchuan_audit_strong_name_first_sentence_v2",
    "leader_region_selector": ".view.TRS_UEDITOR p",
    "name_selector": "strong:first-child",
    "duty_selector": "p",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
    "risk_flag": "仅取段首strong姓名后的第一句职务，排除协助、分管、联系和AB岗",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    text = " ".join(text.split())
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def _clean_name(text: str) -> str:
    return "".join(_clean_text(text).split())


def _strip_leading_name(text: str, name: str) -> str:
    matched = ""
    cut_index = 0
    for index, char in enumerate(text):
        if char.isspace():
            continue
        matched += char
        cut_index = index + 1
        if matched == name:
            return _clean_text(text[cut_index:].lstrip(" ，,、:："))
        if not name.startswith(matched):
            break
    return ""


def parse_page(html: str, base_url: str, rule: dict) -> list[object]:
    """按正文顺序提取段首姓名及其后第一句明确职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in soup.select(rule["leader_region_selector"]):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        strong = paragraph.find("strong")
        name = _clean_name(strong.get_text(" ", strip=True)) if strong else ""
        if not re.fullmatch(r"[一-鿿·]{2,8}", name):
            continue
        remainder = _strip_leading_name(text, name)
        duty_match = re.match(r"(?P<duty>[^。]+。)", remainder)
        if duty_match is None:
            raise RuntimeError(f"姓名 {name} 后缺少明确职务句")
        duty = duty_match.group("duty").rstrip("。").strip()
        if name in seen_names:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=rule["organization"], url=rule["url"], name=name, duty=duty,
                detail_url="", evidence=duty, confidence="high", parser=rule["parser"]
            )
        )
    if not records:
        raise RuntimeError("领导分工正文未解析到姓名职务记录")
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
