from __future__ import annotations
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3215", "domain": "yjj.beijing.gov.cn", "page_type": "多人物详情合并页",
    "structure_group": "beijing_drug_leader_intro_blocks_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_beijing_drug_leader_intro_blocks_v1",
    "risk_flag": "简介与分工同块；仅在当前人物简介段内提取完整现任句，不得混入分工",
    "confidence": "high", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").replace("\u200b", ""))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select(".ldjs-li"):
        name_node = item.select_one(".ld-name a")
        name = clean_text((name_node.get("title", "") or name_node.get_text("", strip=True)) if name_node else "")
        paragraphs = [clean_text(p.get_text("", strip=True)) for p in item.select("p") if "ld-name" not in p.get("class", [])]
        intro = next((text for text in paragraphs if "现任" in text and not text.startswith("分工")), "")
        match = re.search(r"现任[^。]*。", intro)
        evidence = match.group(0) if match else ""
        duty = evidence.removeprefix("现任").removesuffix("。")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty,
                     "confidence": "high", "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "ldjs-li当前人物简介段完整现任句"})
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
