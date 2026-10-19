from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2019",
    "page_type": "人物表格页",
    "structure_group": "nanchang_agriculture_merged_profile_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online",
    "parser": "page_nanchang_agriculture_merged_profile_table_v1",
    "leader_region_selector": "#zoomcon table",
    "name_selector": "人物简介开头、性别字段之前",
    "duty_selector": "同一人物简介中的完整“现任……”句",
    "detail_link_selector": "",
    "risk_flag": "单张表格合并多个人物简介，仅在 #zoomcon 表格正文中按现任句切分",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    """确定性移除表格正文中的全角、半角排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2000-\u200f]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在合并表格正文内按简介句式顺序抽取姓名和现任职务。"""
    del final_url
    if not str(html or "").strip():
        raise RuntimeError("在线入口返回空页面")

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#zoomcon table")
    if not table:
        raise RuntimeError("权威入口未找到 #zoomcon 内的领导表格")
    text = compact_text(table.get_text(" ", strip=True))
    pattern = re.compile(
        r"(?P<name>[\u4e00-\u9fff·]{2,4})[，,](?:男|女)[，,][^。]*?(?P<evidence>现任(?P<duty>[^。]+)。)"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        name = match.group("name")
        duty = match.group("duty").strip("，,。；; ")
        if not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule["organization"]),
                "url": str(page_rule["url"]),
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_nanchang_agriculture_merged_profile_table_v1",
                "selector_summary": "leader=#zoomcon table；name=简介段首；duty=同一简介现任句；detail=none",
            }
        )
    if not rows:
        raise RuntimeError("未从领导表格正文中提取到有效人物简介")
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
