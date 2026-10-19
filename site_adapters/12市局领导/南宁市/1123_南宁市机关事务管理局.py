from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1123",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_government_affairs_article_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_static_http",
    "parser": "page_nanning_government_affairs_article_v2",
    "leader_region_selector": ".nbox p姓名职务标题段",
    "name_selector": "职务边界前姓名",
    "duty_selector": "同一标题段完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "姓名和职务位于同一标题段且姓名、党组等词含字距空白；后续分工段必须排除",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".nbox", "row_selector": ".nbox p"},
        "api": {"enabled": False, "reason": "多人领导分工正文标题段由静态HTML直接提供"},
    },
}


def normalize_layout(text: str) -> str:
    """确定性清理正文标题段中的排版空白。"""
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def clean_status_markers(text: str) -> str:
    """仅删除无期限独立状态标记，保留具体兼任职务及带期限挂职。"""
    marker = r"(?:（(?:兼|挂职|主持日常工作|主持工作)）|\((?:兼|挂职|主持日常工作|主持工作)\)|[<＜](?:兼|挂职)[>＞])"
    return re.sub(marker, "", normalize_layout(text)).strip("，。；、 ")


def split_title(text: str) -> tuple[str, str]:
    """按稳定职务前缀动态切分姓名和职务。"""
    value = normalize_layout(text)
    if value.startswith(("主持", "协助", "负责", "分管")):
        return "", ""
    match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,8})(?P<duty>(?:副局长|市公共资源交易中心|二级调研员).*)$", value)
    if match is None:
        return "", ""
    return match.group("name"), clean_status_markers(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文标题段顺序提取强结构姓名职务原文。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(".nbox p"):
        name, evidence = split_title(paragraph.get_text(" ", strip=True))
        if not name or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".nbox p按DOM顺序；按职务前缀识别姓名职务标题段并排除后续分工段",
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
