from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2679",
    "page_type": "人物表格页",
    "structure_group": "gd_tcm_name_image_duty_blocks_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".article-content",
    "name_selector": ".article-content p strong",
    "duty_selector": ".article-content p strong",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物块顺序为姓名—图片—职务—分工；只取姓名后第一个非空且非职责段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*([，,、：:；;])\s*", r"\1", text)


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按姓名—图片—职务块顺序提取姓名和后续首个职务段。"""
    from bs4 import BeautifulSoup

    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.select(".article-content p")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, paragraph in enumerate(paragraphs):
        name = _clean_name(paragraph.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
            continue
        duty = ""
        for candidate in paragraphs[index + 1 : index + 5]:
            text = _clean_text(candidate.get_text(" ", strip=True))
            if not text:
                continue
            if re.match(r"^(?:分工|分管|联系|负责)[：:]", text):
                break
            if re.fullmatch(r"[\u4e00-\u9fff\s\u3000]{2,8}", text):
                break
            duty = text
            break
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
            }
        )

    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
