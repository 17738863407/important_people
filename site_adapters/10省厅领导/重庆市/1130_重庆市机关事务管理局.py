from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1130", "domain": "jgswj.cq.gov.cn", "page_type": "人物列表完整页",
    "structure_group": "chongqing_affairs_xxgk_cards_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_chongqing_affairs_xxgk_cards_v1",
    "risk_flag": "强结构p1姓名、p2职务；禁止再用职务关键词过滤", "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser"); rows = []
    for card in soup.select("ul.xxgk-fzrxx li"):
        name_node, duty_node, link = card.select_one(".p1"), card.select_one(".p2"), card.select_one("a[href]")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").strip(" ：:，,。")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not evidence or link is None: continue
        rows.append({"name": name, "duty": evidence, "detail_url": urljoin(final_url, link.get("href", "")),
                     "evidence": evidence, "confidence": "high", "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "xxgk-fzrxx卡片p1姓名、p2职务及详情链接"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals()); print(f"输出文件：{output_path}")


if __name__ == "__main__": main()
