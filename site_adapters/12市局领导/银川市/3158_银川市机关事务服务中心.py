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
    "rule_id": "3158",
    "page_type": "多人物详情合并页",
    "structure_group": "yinchuan_profile_final_duty_clause",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "yinchuan_profile_final_duty_clause_v2",
    "leader_region_selector": ".view.TRS_UEDITOR.trs_web.trs_word p",
    "name_selector": "p",
    "duty_selector": "p",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "仅取人物简介末尾中共党员后的明确机构职务句，不拼接工作分工",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    text = " ".join(text.split())
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def parse_page(html: str, base_url: str, rule: dict) -> list[object]:
    """按简介段顺序提取姓名及末尾明确职务句。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in soup.select(rule["leader_region_selector"]):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        match = re.fullmatch(
            r"(?P<name>[一-鿿·]{2,8})[，,]\s*[男女][，,].*?中共党员[，,](?P<duty>[^。]+。)",
            text,
        )
        if match is None:
            continue
        name = match.group("name")
        duty = _clean_text(match.group("duty")).rstrip("。")
        if name in seen_names or not duty:
            raise RuntimeError(f"姓名重复或简介职务异常：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=rule["organization"],
                url=rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导简介正文未解析到姓名职务记录")
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
