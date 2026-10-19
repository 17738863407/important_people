from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3271",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_drc_leader_fullwidth_space_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_drc_leader_fullwidth_space_paragraphs_v2",
    "leader_region_selector": ".zfxxgk_zn",
    "name_selector": ".zfxxgk_zn p全角空格分隔首字段",
    "duty_selector": ".zfxxgk_zn p姓名后的全部原始文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "委领导",
        "end_anchor": "厅级干部末项",
        "include_selectors": [".zfxxgk_zn > p"],
        "exclude_selectors": ["strong分组标题", "空段", "导航", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "姓名和职务以全角空格分隔，二字姓名内部也有全角空格；保留职务中的委字和跨机构任职原文",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".zfxxgk_zn",
            "name_selector": "p全角空格分隔首字段",
            "duty_selector": "p姓名后的全部原始文本",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "委领导",
                "end_anchor": "厅级干部末项",
                "include_selectors": [".zfxxgk_zn > p"],
                "exclude_selectors": ["strong分组标题", "空段", "导航", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML领导区域直接提供姓名和职务段落"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "zfxxgk_zn" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _split_person_line(value: str) -> tuple[str, str] | None:
    raw = str(value or "").replace("\xa0", " ").strip()
    parts = [_clean_text(part) for part in re.split(r"\u3000+", raw)]
    parts = [part for part in parts if part]
    if len(parts) < 2:
        return None
    if len(parts) >= 3 and len(parts[0]) == 1 and len(parts[1]) == 1:
        name = parts[0] + parts[1]
        duty = " ".join(parts[2:])
    else:
        name = re.sub(r"\s+", "", parts[0])
        duty = " ".join(parts[1:])
    duty = duty.strip(" ：:，,。.；;")
    if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not duty:
        return None
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".zfxxgk_zn")
    if region is None or _is_hidden(region):
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.find_all("p", recursive=False):
        if paragraph.select_one("strong") is not None or _is_hidden(paragraph):
            continue
        parsed = _split_person_line(paragraph.get_text("", strip=True))
        if parsed is None:
            continue
        name, duty = parsed
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_yunnan_drc_leader_fullwidth_space_paragraphs_v2",
                "selector_summary": ".zfxxgk_zn直接p；全角空格分隔姓名与完整职务",
            }
        )
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
