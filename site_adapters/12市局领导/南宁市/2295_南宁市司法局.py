from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2295",
    "page_type": "多人物详情合并页",
    "structure_group": "nanning_justice_top_roster_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_http",
    "parser": "page_nanning_justice_top_roster_v2",
    "leader_region_selector": "#UCAP-CONTENT",
    "name_selector": "正文顶部姓名职务清单中机构名前缀之前",
    "duty_selector": "正文顶部姓名职务清单完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "顶部现任清单后重复展示个人简介和分工；必须只接受含完整机构名的短清单段并保持首次DOM顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#UCAP-CONTENT", "name_selector": "短清单段机构名前", "duty_selector": "同一短清单段完整原文"}, "api": {"enabled": False, "reason": "静态正文顶部直接提供姓名职务清单"}},
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def parse_roster_line(text: str) -> tuple[str, str, str]:
    value = normalize_layout(text)
    marker = "南宁市司法局"
    split_at = value.find(marker)
    if split_at < 2 or len(value) > 100:
        return "", "", ""
    name = value[:split_at].replace(" ", "")
    if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None:
        return "", "", ""
    # 顶部短清单固定为“姓名 + 机构名 + 职务”。姓名仅在与当前记录完全
    # 一致且位于原文开头时剥离，保留机构名称和全部职务语义作为依据说明。
    evidence = value[len(name):].lstrip(" 、，:：-—")
    return name, value, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#UCAP-CONTENT")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        name, raw_evidence, evidence = parse_roster_line(paragraph.get_text(" ", strip=True))
        if not name or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "#UCAP-CONTENT顶部姓名职务短清单按DOM顺序；仅移除开头的完全匹配姓名，保留机构和原始职务"})
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
