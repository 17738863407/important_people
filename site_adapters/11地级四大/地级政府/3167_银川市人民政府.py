from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3167",
    "page_type": "人物分组卡片页",
    "structure_group": "主卡片与分组人物链接",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "YinchuanGovernmentLeaderGroupedCardParser_v2",
    "leader_region_selector": ".zfxxgk_zdgkc dl",
    "name_selector": "a[href][title]",
    "duty_selector": "dt p, dd .stitle",
    "detail_link_selector": "a[href][title]",
    "risk_flag": "主卡片职务姓名同一文本，其他人物共用分组职务标题",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """归一网页排版空白。"""
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(text: str) -> str:
    """姓名字段仅去除排版空白。"""
    return "".join(_clean_text(text).split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按主卡片及后续分组的DOM顺序解析领导信息。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(rule["leader_region_selector"])
    if root is None:
        return []

    records: list[dict] = []
    main_card = root.select_one(":scope > dt")
    if main_card is not None:
        link = main_card.select_one(rule["detail_link_selector"])
        label_node = main_card.select_one("p")
        label = _clean_text(label_node.get_text(" ", strip=True) if label_node else "")
        name = _clean_name(link.get("title") or link.get_text(" ", strip=True) if link else "")
        duty = _clean_text(label.split("：", 1)[0] if "：" in label else "")
        href = (link.get("href") or "").strip() if link else ""
        if name and duty:
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(base_url, href) if href else "",
                    "parser": rule["parser"],
                    "selector_summary": "dl > dt：a[title]姓名，p组合职务姓名",
                }
            )

    for group in root.select(":scope > dd"):
        title_node = group.select_one(":scope > .stitle")
        evidence = _clean_text(title_node.get_text(" ", strip=True) if title_node else "")
        if not evidence:
            continue
        for link in group.select(":scope > a[href][title]"):
            name = _clean_name(link.get("title") or link.get_text(" ", strip=True))
            href = (link.get("href") or "").strip()
            if not name:
                continue
            records.append(
                {
                    "name": name,
                    "duty": evidence,
                    "evidence": evidence,
                    "detail_url": urljoin(base_url, href) if href else "",
                    "parser": rule["parser"],
                    "selector_summary": "dl > dd：.stitle分组职务，a[title]姓名与详情",
                }
            )
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
