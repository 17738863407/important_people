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
    "rule_id": "2836",
    "page_type": "动态人物表格页",
    "structure_group": "渲染后职务分组表格",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom",
    "collector": "playwright_hidden",
    "parser": "TaiyuanCppccRenderedLeaderTableParser_v2",
    "leader_region_selector": "table#leaderMore > tbody > tr",
    "risk_flag": "原始HTML领导表为空，渲染后含一行无姓名的兼任职务，必须跳过空行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一表格换行与排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(value: str) -> str:
    """姓名字段仅去除排版空白。"""
    return "".join(_clean_text(value).split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按渲染表格行和单元格顺序展开职务分组人物。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for table_row in soup.select(rule["leader_region_selector"]):
        cells = table_row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        evidence = _clean_text(cells[0].get_text(" ", strip=True))
        if not evidence:
            continue
        for link in cells[1].select("a[href]"):
            name = _clean_name(link.get_text(" ", strip=True))
            href = (link.get("href") or "").strip()
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
                continue
            seen.add(name)
            records.append(
                {
                    "name": name,
                    "duty": evidence,
                    "evidence": evidence,
                    "detail_url": urljoin(base_url, href) if href else "",
                    "parser": rule["parser"],
                    "selector_summary": "渲染后table#leaderMore行：首格职务、次格人物链接",
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
