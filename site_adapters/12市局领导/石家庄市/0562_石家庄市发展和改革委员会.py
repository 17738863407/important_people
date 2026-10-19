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
    "rule_id": "0562", "page_type": "人物列表完整页", "structure_group": "sjz_development_reform_colon_lines_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_development_reform_colon_lines_v2",
    "leader_region_selector": "div#conN", "name_selector": "直接子div冒号前",
    "duty_selector": "直接子div冒号后", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名排版空白须移除；职务页面标点应保留",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def clean_evidence(value: str) -> str:
    """删除句末句号和无期限的独立状态标记，保留带期限的挂职信息。"""
    text = re.sub(r"[（(]\s*(?:挂职|兼|主持日常工作)\s*[）)]", "", clean_text(value))
    return text.rstrip("。 ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文直接子div顺序解析冒号分隔的姓名和原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("div#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    records: list[object] = []
    seen_names: set[str] = set()
    for node in regions[0].find_all("div", recursive=False):
        text = clean_text(node.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u3400-\u9fff· ]{2,20})\s*[:：]\s*(?P<duty>.+)", text)
        if match is None:
            raise RuntimeError(f"领导行缺少姓名职务冒号结构：{text}")
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = clean_evidence(match.group("duty"))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or name in seen_names:
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
