from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    """压缩简介中的排版空白，不改变原文语义。"""
    value = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    value = " ".join(value.split())
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    value = re.sub(r"\s+([，。；：、（）])", r"\1", value)
    return re.sub(r"([，。；：、（）])\s+", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析领导简介首段；工作分工不作为主职务依据。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []

    for paragraph in soup.select(".view.TRS_UEDITOR.trs_web p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        strong = paragraph.find("strong")
        strong_text = clean_text(strong.get_text(" ", strip=True) if strong else "")
        name = re.sub(r"[，,、：:\s]+$", "", strong_text)
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or "工作" in name or "分工" in name:
            continue

        match = re.search(r"现任[^。]*。", text)
        evidence = (
            re.sub(
                r"^现任(?:职务)?(?:\s*[：:]\s*)?\s*",
                "",
                clean_text(match.group(0)),
                count=1,
            )
            if match
            else ""
        )
        records.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high" if evidence else "medium",
                "parser": "page_inline_yinchuan_resource_profiles_v1",
            }
        )
    return records


PAGE_RULE = {
    "rule_id": "3156",
    "page_type": "多人物详情合并页",
    "structure_group": "yinchuan_resource_profile_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_resource_profiles_v1",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "简介与工作分工段交替；无现任句的人物保留明确姓名并将依据说明留空",
    "confidence": "high",
}


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
