from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2782",
    "page_type": "人物目录详情页",
    "structure_group": "nanchang_sports_name_profile_sequence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online",
    "parser": "page_nanchang_sports_name_profile_sequence_v1",
    "leader_region_selector": "#zoom > p",
    "name_selector": "简介前独立姓名段落",
    "duty_selector": "同一简介中的南昌市体育局职务片段",
    "detail_link_selector": "",
    "risk_flag": "姓名与简介使用相邻段落，职务后紧接主持或分管说明",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩正文中的全角和半角排版空白。"""
    text = re.sub(r"[\s\u3000\u00a0\u2000-\u200f]+", " ", str(value or ""))
    return re.sub(r"\s*([、，,。；;])\s*", r"\1", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按 #zoom 直接子段落顺序关联独立姓名和人物简介。"""
    del final_url
    if not str(html or "").strip():
        raise RuntimeError("在线入口返回空页面")

    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#zoom")
    if not root:
        raise RuntimeError("权威入口未找到领导信息容器 #zoom")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pending_name = ""
    for paragraph in root.select(":scope > p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        compact = re.sub(r"\s+", "", text)
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", compact):
            pending_name = compact
            continue
        if not pending_name or not re.match(r"^(?:男|女)[，,]", compact):
            continue
        duty_match = re.search(
            r"(?P<evidence>南昌市体育局(?P<duty>.+?))(?=[，,](?:主持|分管)|。|$)",
            compact,
        )
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
                    "duty": duty_match.group("evidence"),
                    "detail_url": "",
                    "evidence": duty_match.group("evidence"),
                    "confidence": "high",
                    "parser": "page_nanchang_sports_name_profile_sequence_v1",
                    "selector_summary": "leader=#zoom > p；name=独立姓名段；duty=相邻简介体育局职务；detail=none",
                }
            )
        pending_name = ""
    if not rows:
        raise RuntimeError("未从相邻姓名与人物简介段落中提取到有效领导信息")
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
