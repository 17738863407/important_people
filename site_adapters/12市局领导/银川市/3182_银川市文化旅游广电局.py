from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    """压缩正文的排版空白。"""
    value = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    value = " ".join(value.split())
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    value = re.sub(r"\s+([，。；：、（）])", r"\1", value)
    return re.sub(r"([，。；：、（）])\s+", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从“姓名，职务：分工”段落中仅提取姓名与冒号前原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    pattern = re.compile(r"^(.{2,8}?)\s*[，,]\s*(.+?)\s*[：:]")

    for paragraph in soup.select(".view.TRS_UEDITOR p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = pattern.match(text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        duty = clean_text(match.group(2))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty:
            continue
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_yinchuan_culture_roles_v1",
            }
        )
    return records


PAGE_RULE = {
    "rule_id": "3182",
    "page_type": "人物列表完整页",
    "structure_group": "yinchuan_culture_name_role_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_culture_roles_v1",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "冒号后为工作分工；末段 AB 岗说明不是人物记录",
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
