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
    "rule_id": "3046", "domain": "xfb.beijing.gov.cn", "page_type": "人物列表完整页",
    "structure_group": "beijing_petition_article_paragraphs_v2", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_beijing_petition_article_paragraphs_v2",
    "risk_flag": "正文含空段落、空strong及姓名嵌套层级差异；按每段首个非空合法strong定位姓名",
    "confidence": "high", "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").replace("\u200b", ""))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for paragraph in soup.select("#div_zhengwen p"):
        names = [compact_text(node.get_text("", strip=True)) for node in paragraph.select("strong")]
        name = next((value for value in names if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", value)), "")
        full_text = compact_text(paragraph.get_text("", strip=True))
        duty = full_text.replace(name, "", 1) if name else ""
        if not name or not duty:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty,
                     "confidence": "high", "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "div_zhengwen人物段落首个非空strong姓名与段落剩余职务"})
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
