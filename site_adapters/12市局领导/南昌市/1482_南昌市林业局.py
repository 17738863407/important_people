from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1482",
    "page_type": "多人物详情合并页",
    "structure_group": "nanchang_forestry_name_profile_sequence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online",
    "parser": "page_nanchang_forestry_name_profile_sequence_v1",
    "leader_region_selector": "p, blockquote > span",
    "name_selector": "人物简介前最近的独立居中姓名段落",
    "duty_selector": "同一人物简介中的完整“现任……”句",
    "detail_link_selector": "",
    "risk_flag": "页面按姓名、简介、分工重复排版，仅关联相邻姓名与简介，不读取分工段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    """确定性移除正文排版空白，修复被 span 拆开的姓名和机构字样。"""
    return re.sub(r"[\s\u3000\u00a0\u2000-\u200f]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序关联独立姓名段与紧随其后的现任职务简介。"""
    del final_url
    if not str(html or "").strip():
        raise RuntimeError("在线入口返回空页面")

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pending_name = ""
    for block in soup.select("p, blockquote > span"):
        text = compact_text(block.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", text):
            pending_name = text
            continue
        if not pending_name or "现任" not in text or not re.match(r"^(?:男|女)[，,]", text):
            continue
        duty_match = re.search(r"(?P<evidence>现任(?P<duty>[^。]+)。)", text)
        if not duty_match:
            continue
        duty = duty_match.group("duty").strip("，,。；; ")
        if duty and pending_name not in seen:
            seen.add(pending_name)
            rows.append(
                {
                    "organization": str(page_rule["organization"]),
                    "url": str(page_rule["url"]),
                    "name": pending_name,
                    "duty": duty,
                    "detail_url": "",
                    "evidence": duty,
                    "confidence": "high",
                    "parser": "page_nanchang_forestry_name_profile_sequence_v1",
                    "selector_summary": "leader=p, blockquote > span；name=简介前独立姓名段；duty=同一简介现任句；detail=none",
                }
            )
        pending_name = ""
    if not rows:
        raise RuntimeError("未从领导页面相邻姓名与简介段落中提取到有效人物")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
