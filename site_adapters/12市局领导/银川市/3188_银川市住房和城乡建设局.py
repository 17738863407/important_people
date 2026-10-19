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
    "rule_id": "3188",
    "page_type": "人物列表完整页",
    "structure_group": "yinchuan_profile_position_sentence_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_profile_position_sentence_v2",
    "leader_region_selector": ".view.TRS_UEDITOR p",
    "name_selector": "人物简介段开头、性别字段之前",
    "duty_selector": "人物简介段末尾职务句或完整现任句",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "工作分工是相邻独立段，不得并入职务；姓名可能含排版空格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    text = " ".join(text.split())
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def _clean_name(text: str) -> str:
    return re.sub(r"[，,、：:\s]+$", "", "".join(_clean_text(text).split()))


def _extract_name(text: str) -> str:
    match = re.match(r"^(.{2,8}?)[，,]\s*[男女]", text)
    return _clean_name(match.group(1)) if match else ""


def _extract_position(text: str) -> str:
    if "现任" in text:
        match = re.search(r"现任[^。]*。", text)
        if match:
            return _clean_text(match.group(0)).removeprefix("现任").removesuffix("。").strip()
    parts = [part for part in re.split(r"[；。]", text) if part.strip()]
    if not parts:
        return ""
    position = _clean_text(parts[-1])
    if not any(keyword in position for keyword in ["局长", "主任", "委员", "调研员", "书记"]):
        return ""
    return position + ("。" if text.rstrip().endswith("。") else "")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析银川市住房和城乡建设局领导简介和工作分工。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for paragraph in soup.select(".view.TRS_UEDITOR p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        name = _extract_name(text)
        if name:
            evidence = _extract_position(text)
            if not evidence:
                continue
            records.append(
                {
                "organization": str(rule.get("organization") or ""),
                "url": str(rule.get("url") or "") or base_url,
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high",
                "parser": rule["parser"],
                "selector_summary": (
                    "strategy=custom_parse_page；leader=.view.TRS_UEDITOR p；"
                    "name=简介开头性别前姓名；duty=简介末句或完整现任句"
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
