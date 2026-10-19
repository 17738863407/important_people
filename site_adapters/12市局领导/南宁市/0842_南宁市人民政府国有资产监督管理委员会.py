from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0842",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_sasac_article_leader_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_static_http",
    "parser": "page_nanning_sasac_article_leader_v2",
    "leader_region_selector": ".trs_editor_view p strong",
    "name_selector": "加粗行职务边界前姓名",
    "duty_selector": "同一加粗行原始姓名职务节点",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "姓名与职务在同一加粗行且姓名含字距空白；当前页为多人合并页，不得写作个人详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".trs_editor_view p strong", "row_selector": ".trs_editor_view p strong"},
        "api": {"enabled": False, "reason": "多人领导信息正文的加粗姓名职务行由静态HTML直接提供"},
    },
}


def normalize_layout(text: str) -> str:
    """确定性清理富文本编辑器产生的排版空白。"""
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def split_title(text: str) -> tuple[str, str]:
    """按稳定职务前缀切分加粗行中的姓名和职务。"""
    value = normalize_layout(text)
    match = re.match(r"^(?P<name>[\u4e00-\u9fff\s·]{2,12}?)(?P<duty>(?:党委书记|副主任|四级调研员).*)$", value)
    if match is None:
        return "", ""
    name = re.sub(r"\s+", "", match.group("name"))
    if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None:
        return "", ""
    return name, normalize_layout(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文加粗姓名职务行顺序提取强结构原文。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for strong in soup.select(".trs_editor_view p strong"):
        name, duty = split_title(strong.get_text(" ", strip=True))
        if not name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".trs_editor_view p strong按DOM顺序；按职务前缀切分姓名并保留同一加粗行完整原文",
            }
        )
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
