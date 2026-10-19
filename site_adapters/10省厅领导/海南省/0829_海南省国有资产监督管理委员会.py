from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩网页字段中的排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析委领导区域中以换行分隔姓名和职务的链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate(soup.select("a.name[href*='/ldxx/wld/']"), start=1):
        parts = [clean_text(text) for text in link.stripped_strings if clean_text(text)]
        if len(parts) < 2:
            continue
        name = parts[0].replace(" ", "")
        duty = "；".join(parts[1:])
        duty = re.sub(r"[（(]\s*挂职\s*[）)]", "", duty)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
                "source_order": str(source_order),
                "confidence": "high",
                "parser": "page_inline_hainan_sasac_name_break_duty_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0829",
    "page_type": "人物列表完整页",
    "structure_group": "海南国资委委领导换行链接",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_hainan_sasac_name_break_duty_v2",
    "leader_region_selector": "a.name[href*='/ldxx/wld/']",
    "name_selector": "a.name[href*='/ldxx/wld/']",
    "duty_selector": "a.name[href*='/ldxx/wld/']",
    "detail_link_selector": "a.name[href*='/ldxx/wld/']",
    "detail_strategy": {
        "required": False,
        "mode": "same_anchor_detail",
        "detail_collector_type": "none",
    },
    "risk_flag": "同一a.name内首个文本为姓名、br后的剩余文本为职务，仅限定委领导wld详情路径",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
