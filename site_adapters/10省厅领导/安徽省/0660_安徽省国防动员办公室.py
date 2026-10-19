from __future__ import annotations

import re
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
    "rule_id": "0660", "page_type": "人物列表完整页",
    "structure_group": "安徽省国防动员办领导列表", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "anhui_gdb_leader_list_links_v2",
    "leader_region_selector": "a.left[href*='/jgld/jgsz/bld/']",
    "name_selector": "链接文本末尾姓名", "duty_selector": "链接文本姓名前职务",
    "detail_link_selector": "a.left[href*='/jgld/jgsz/bld/']",
    "risk_flag": "链接文本为职务加姓名，仅在领导路径内解析", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for link in soup.select("a.left[href*='/jgld/jgsz/bld/']"):
        text = clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff·]{2,4})", text)
        if not match:
            continue
        duty, name = clean_text(match.group("duty")), match.group("name")
        rows.append({
            "organization": page_rule["organization"], "url": page_rule["url"],
            "name": name, "duty": duty,
            "detail_url": urljoin(final_url, str(link.get("href") or "")), "evidence": duty,
            "confidence": "high", "parser": "anhui_gdb_leader_list_links_v2",
            "selector_summary": "strategy=custom_parse_page；item=a.left[href*=/jgld/jgsz/bld/]；split=链接文本末尾姓名",
        })
    if not rows:
        raise RuntimeError("安徽省国防动员办领导列表未抽取到人物")
    return rows


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
