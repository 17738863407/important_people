from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {"rule_id": "4153", "page_type": "rendered_leader_text", "load_mode": "browser", "fetch_mode": "online", "parser": "page_specific", "inline_parser_handles_fetch": True, "inline_fetch_collector": "playwright", "confidence": "high", "risk_notes": "HTTP 仅返回万网脚本壳，需由页面专属解析器读取 Playwright 渲染后的领导文本。"}


def parse_page(html: str, page_url: str, rule: dict) -> list[dict]:
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    rendered = fetch_html_with_strategy(page_url, strategy="playwright", timeout=45).html
    soup = BeautifulSoup(rendered, "html.parser")
    rows: list[dict] = []
    for node in soup.select("span[style*='font-size']"):
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True).replace("\u3000", " ")).strip()
        parts = text.split()
        if len(parts) < 2:
            continue
        if len(parts) >= 3 and all(re.fullmatch(r"[\u4e00-\u9fff]", item) for item in parts[:2]):
            name, duty = "".join(parts[:2]), "".join(parts[2:])
        else:
            name, duty = parts[0], "".join(parts[1:])
        if any(token in duty for token in ("所长", "工程师", "书记")):
            rows.append({"name": name, "duty": duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("渲染后的现任领导页面未解析出姓名和职务")
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
