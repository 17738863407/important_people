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
    "rule_id": "3160",
    "page_type": "人物列表完整页",
    "structure_group": "yinchuan_leader_title_colon_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_leader_title_colon_v2",
    "leader_region_selector": ".view.TRS_UEDITOR.trs_web p",
    "name_selector": "冒号前标题末尾姓名",
    "duty_selector": "冒号前标题的姓名前缀",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "冒号后为分工而非职务；二级调研员存在排版空格，只取冒号前原始职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    text = " ".join(text.split())
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def _split_title(title: str) -> tuple[str, str]:
    title = _clean_text(title).strip(" ：:")
    forbidden = set("局副委组党工记长员级、，：:()（）")
    for length in (4, 3, 2):
        if len(title) <= length:
            continue
        candidate = title[-length:]
        if any(char in forbidden for char in candidate):
            continue
        position = _clean_text(title[:-length])
        if position and any(keyword in position for keyword in ["局长", "主任", "委员", "调研员", "书记"]):
            return candidate, position
    return "", ""


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析银川市科学技术局领导分工标题段。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for paragraph in soup.select(".view.TRS_UEDITOR.trs_web p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if "：" not in text and ":" not in text:
            continue
        title, _ = re.split(r"[:：]", text, maxsplit=1)
        if not any(keyword in title for keyword in ["局长", "主任", "委员", "调研员", "书记"]):
            continue
        name, position = _split_title(title)
        if not name or not position:
            continue
        records.append(
            {
                "organization": str(rule.get("organization") or ""),
                "url": str(rule.get("url") or "") or base_url,
                "name": name,
                "duty": position,
                "detail_url": "",
                "evidence": position,
                "confidence": "high",
                "parser": rule["parser"],
                "selector_summary": (
                    "strategy=custom_parse_page；leader=.view.TRS_UEDITOR.trs_web p；"
                    "name=冒号前标题末尾姓名；duty=冒号前姓名之前的原始职务"
                ),
            }
        )
    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
