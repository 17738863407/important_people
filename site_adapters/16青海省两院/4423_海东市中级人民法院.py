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
    "rule_id": "4423",
    "page_type": "领导简历标签字段文章",
    "structure_group": "qinghai_court_labeled_profile_blocks_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "custom_parse_page",
    "parser": "qinghai_court_labeled_profile_blocks_v1",
    "leader_region_selector": ".detail > .text",
    "name_selector": ".detail > .text > p中的姓名字段",
    "duty_selector": ".detail > .text > p中的现任职务字段",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "每人字段跨多个相邻段落；按姓名字段至随后现任职务字段严格配对，图片不是人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理字段排版空白及中文标点两侧空格。"""
    cleaned = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([，。；、：])\s*", r"\1", cleaned)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按文章段落顺序配对姓名字段及其后的现任职务字段。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    article = soup.select_one(".detail > .text")
    if article is None:
        raise RuntimeError("未定位到法院文章正文")

    records: list[object] = []
    seen_names: set[str] = set()
    current_name = ""
    for paragraph in article.select(":scope > p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if text.startswith("姓名："):
            if current_name:
                raise RuntimeError(f"人物字段缺少现任职务：{current_name}")
            current_name = re.sub(r"\s+", "", clean_text(text.removeprefix("姓名：")))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", current_name):
                raise RuntimeError("姓名字段格式异常")
            if current_name in seen_names:
                raise RuntimeError(f"人物姓名重复：{current_name}")
            continue

        if not text.startswith("现任职务："):
            continue
        if not current_name:
            raise RuntimeError("现任职务字段之前未找到对应姓名字段")
        evidence = clean_text(text.removeprefix("现任职务：")).rstrip("。；; ")
        if not evidence:
            raise RuntimeError(f"现任职务字段为空：{current_name}")

        seen_names.add(current_name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=current_name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
        current_name = ""

    if current_name:
        raise RuntimeError(f"人物字段缺少现任职务：{current_name}")
    if not records:
        raise RuntimeError("当前文章未提取到姓名与现任职务字段")
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
