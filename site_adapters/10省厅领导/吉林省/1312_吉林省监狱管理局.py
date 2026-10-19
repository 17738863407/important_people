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
    "rule_id": "1312",
    "domain": "jyj.jl.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jilin_prison_single_leader_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "single_detail_direct",
    "collector": "static_http",
    "parser": "page_inline_jilin_prison_single_leader_detail_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口本身为唯一领导详情页，详情链接必须留空并排除后续履历段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从唯一现职段落提取姓名和完整职务，不扫描个人简介与履历。"""
    soup = BeautifulSoup(html, "html.parser")
    for paragraph in soup.select(".TRS_Editor p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if "监狱管理局" not in text or "党组" not in text:
            continue
        match = re.fullmatch(r"([\u3400-\u9fff·]{2,5})\s+(.+)", text)
        if match is None:
            continue
        name = match.group(1)
        duty = clean_text(match.group(2)).strip("，,；;。 ")
        duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty).strip("，,；;。 ")
        if not duty:
            continue
        return [
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；region=.TRS_Editor p；"
                    "field=current-duty-paragraph name duty；detail=none"
                ),
            }
        ]
    return []


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
