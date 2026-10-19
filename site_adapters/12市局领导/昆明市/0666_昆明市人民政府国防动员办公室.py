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
    "rule_id": "0666",
    "page_type": "多人物详情合并页",
    "structure_group": "kunming_gdb_inline_present_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_gdb_inline_present_paragraphs_v2",
    "leader_region_selector": ".content p",
    "name_selector": ".content p",
    "duty_selector": ".content p",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "max_detail_links": 0,
    },
    "risk_flag": "姓名、简历、历任和现任分段排列，只接受独立姓名段后的现任段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u00a0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """将独立姓名段与随后同人物的现任段一一对应。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".content") or soup
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    current_name = ""
    for paragraph in content.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        compact = re.sub(r"\s+", "", text)
        if re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", compact):
            current_name = compact
            continue
        if current_name and text.startswith("现任"):
            if current_name not in seen:
                duty = re.sub(r"^现任\s*", "", text)
                duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty)
                duty = re.sub(r"\s*([、，,；;：:])\s*", r"\1", duty).removesuffix("。").strip()
                seen.add(current_name)
                rows.append(
                    {
                        "name": current_name,
                        "duty": duty,
                        "detail_url": "",
                        "evidence": duty,
                        "confidence": "high",
                        "parser": page_rule["parser"],
                    }
                )
            current_name = ""
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
