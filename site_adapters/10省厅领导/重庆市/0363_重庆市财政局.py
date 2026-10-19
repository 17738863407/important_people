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
    "rule_id": "0363", "domain": "czj.cq.gov.cn", "page_type": "职务分组名单页",
    "structure_group": "chongqing_finance_ld_ul_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_chongqing_finance_ld_ul_v1",
    "risk_flag": "每人同时有图片与姓名链接；职务原文含机构前缀，不得删除",
    "confidence": "high", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"\s*([、，,；;：:])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select("ul.ld-ul > li"):
        link = item.select_one("a.name[href]")
        name = clean_text(link.get_text(" ", strip=True) if link else "")
        evidence = clean_text(item.get_text(" ", strip=True))
        duty = clean_text(evidence.replace(name, "", 1)) if name else ""
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty or link is None:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link.get("href", "")),
                     "evidence": duty, "confidence": "high", "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "ld-ul人物项name链接及保留机构前缀的原始职务"})
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
