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
    "rule_id": "3016", "page_type": "多人物详情合并页", "structure_group": "xian_gov_office_current_sentence_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page", "parser": "xian_gov_office_current_sentence_v2",
    "leader_region_selector": "#article", "name_selector": "人物段落首个逗号前",
    "duty_selector": "人物段落内现任完整句", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "正文按人物顺序交替出现简介、分工等段落，只在#article内含现任的当前人物段落提取完整现任句",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.models import PersonRecord
    soup = BeautifulSoup(html or "", "html.parser")
    article = soup.select_one("#article")
    if article is None:
        raise RuntimeError("未定位到领导信息正文#article")
    records: list[object] = []
    seen: set[str] = set()
    for paragraph in article.find_all("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        current_match = re.search(r"现任[^。]*。", text)
        if current_match is None:
            continue
        name_match = re.match(r"(?P<name>[\u3400-\u9fff·]{2,20})[，,]", text)
        if name_match is None:
            raise RuntimeError(f"现任人物段落姓名边界异常：{text[:80]}")
        name = name_match.group("name")
        evidence = re.sub(
            r"^现任(?:职务)?\s*[：:]?\s*",
            "",
            current_match.group(0),
        ).strip()
        if name in seen:
            raise RuntimeError(f"现任人物重复：{name}")
        seen.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("领导信息正文没有可验证现任人物段落")
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
