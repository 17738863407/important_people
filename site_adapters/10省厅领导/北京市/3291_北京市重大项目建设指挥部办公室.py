from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3291", "domain": "zdb.beijing.gov.cn", "page_type": "人物列表完整页",
    "structure_group": "beijing_major_projects_leader_cards_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_beijing_major_projects_leader_cards_v1",
    "risk_flag": "页面另含日期文本；仅解析nr_box内h4姓名和p职务，并动态取得外层详情链接",
    "confidence": "high", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".nr_box:has(h4):has(p)"):
        name = re.sub(r"\s+", "", clean_text(card.select_one("h4").get_text(" ", strip=True)))
        evidence = clean_text(card.select_one("p").get_text(" ", strip=True))
        duty = evidence.removesuffix("。").strip()
        link = card.find_parent("a", href=True)
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty or link is None:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link.get("href", "")),
                     "evidence": evidence, "confidence": "high", "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "nr_box内h4姓名、p职务及外层人物详情链接"})
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
