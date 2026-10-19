from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2726",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "局领导链接组",
    "row_selector": "a[href]中以河南省统计局开头的链接",
    "name_selector": "链接文本最后一个空格分隔字段",
    "duty_selector": "链接文本中机构后、姓名前文本",
    "detail_link_selector": "当前人物链接href",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "页面没有稳定人物类名，以完整机构前缀及职务姓名分隔空格限定当前领导链接。",
}


def normalize_text(text: str) -> str:
    """仅压缩链接文本中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按局领导链接DOM顺序拆分明确的机构、职务和姓名字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    organization_prefix = "河南省统计局"

    for link in soup.find_all("a", href=True):
        evidence = normalize_text(link.get_text(" ", strip=True))
        if not evidence.startswith(organization_prefix):
            continue
        after_prefix = evidence[len(organization_prefix) :].strip()
        if " " not in after_prefix:
            continue
        duty, name = after_prefix.rsplit(" ", maxsplit=1)
        duty = duty.strip("：:，,。；; ")
        name = name.strip()
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, str(link.get("href") or "")),
                "evidence": f"{organization_prefix}{duty}",
            }
        )

    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
