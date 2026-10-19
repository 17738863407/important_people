from __future__ import annotations
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0607", "domain": "gaj.cq.gov.cn", "page_type": "人物列表完整页",
    "structure_group": "chongqing_police_ldxx_cards_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_chongqing_police_ldxx_cards_v1",
    "risk_flag": "仅解析ldxx-container人物卡片内name与info字段", "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_evidence(value: str) -> str:
    """删除括号内独立状态词，保留同括号的职级等有效内容。"""
    def clean_parenthesis(match: re.Match[str]) -> str:
        parts = [part.strip() for part in re.split(r"[，,]", match.group(1))]
        kept = [part for part in parts if part and part not in {"兼", "主持日常工作"}]
        return f"（{'，'.join(kept)}）" if kept else ""

    return re.sub(r"[（(]([^（）()]*)[）)]", clean_parenthesis, clean_text(value)).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".ldxx-container .item"):
        name_node, duty_node = card.select_one(".infos .name"), card.select_one(".infos .info")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        evidence = clean_evidence(duty_node.get_text(" ", strip=True) if duty_node else "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not evidence: continue
        rows.append({"name": name, "duty": evidence, "detail_url": "", "evidence": evidence,
                     "confidence": "high", "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "ldxx-container卡片name姓名与info职务"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__": main()
