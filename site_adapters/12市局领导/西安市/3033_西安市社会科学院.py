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
    "rule_id": "3033", "page_type": "人物列表完整页", "structure_group": "xian_social_science_label_paragraphs_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page", "parser": "xian_social_science_label_paragraphs_v2",
    "leader_region_selector": ".content_brower", "name_selector": "p姓名标签值",
    "duty_selector": "后续p职务标签值", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "正文内姓名与职务分列于相邻标签段落，按段落DOM顺序配对；只做排版空白清理",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    from crawler_core.models import PersonRecord
    soup = BeautifulSoup(html or "", "html.parser")
    container = soup.select_one(".content_brower")
    if container is None:
        raise RuntimeError("未定位到领导信息正文.content_brower")
    records: list[object] = []
    pending_name = ""
    seen: set[str] = set()
    for paragraph in container.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        name_match = re.fullmatch(r"姓名\s*[：:]\s*(?P<name>[\u3400-\u9fff·]{2,20})", text)
        duty_match = re.fullmatch(r"职务\s*[：:]\s*(?P<duty>.+)", text)
        if name_match:
            if pending_name:
                raise RuntimeError(f"人物{pending_name}后未出现职务段落")
            pending_name = name_match.group("name")
        elif duty_match and pending_name:
            evidence = duty_match.group("duty")
            if pending_name in seen:
                raise RuntimeError(f"领导姓名重复：{pending_name}")
            seen.add(pending_name)
            records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=pending_name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
            pending_name = ""
    if pending_name:
        raise RuntimeError(f"人物{pending_name}缺少职务段落")
    if not records:
        raise RuntimeError("领导信息正文没有可验证姓名职务段落")
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
