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
    "rule_id": "0674",
    "page_type": "多人物详情合并页",
    "structure_group": "gdcss_inline_current_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "div.mainbox_bg.content",
    "name_selector": "div.mainbox_bg.content p",
    "duty_selector": "div.mainbox_bg.content p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物简介含学历党派信息，仅在各人物段内提取完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """逐人物段落提取段首姓名和完整“现任……”句。"""
    from bs4 import BeautifulSoup

    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for paragraph in soup.select("div.mainbox_bg.content p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        name_part = re.split(r"[，,]", text, maxsplit=1)[0]
        name = re.sub(r"\s+", "", name_part)
        current_match = re.search(r"现任[^。]*。", text)
        if (
            not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name)
            or current_match is None
            or name in seen
        ):
            continue
        evidence = current_match.group(0)
        duty = evidence.removeprefix("现任").removesuffix("。").strip()
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
