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
    "rule_id": "0711", "domain": "ghzrzyj.cq.gov.cn", "page_type": "人物列表完整页",
    "structure_group": "chongqing_natural_resources_responsible_cards_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_chongqing_natural_resources_responsible_cards_v1",
    "risk_flag": "仅解析jgzn-fzrxx负责人卡片的name、job和详情链接", "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser"); rows = []
    for card in soup.select("ul.jgzn-fzrxx.clearfix > li"):
        name_node, duty_node, link = card.select_one("p.name"), card.select_one("p.job"), card.select_one("a[href]")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not evidence or link is None: continue
        rows.append({"name": name, "duty": evidence, "detail_url": urljoin(final_url, link.get("href", "")),
                     "evidence": evidence, "confidence": "high", "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "jgzn-fzrxx卡片name、job及详情链接"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals()); print(f"输出文件：{output_path}")


if __name__ == "__main__": main()
