from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0654",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "ul#lingdaobz",
    "row_selector": "ul#lingdaobz > li",
    "name_selector": "p.text-right a[href][title]",
    "duty_selector": "h5 span",
    "detail_link_selector": "p.text-right a[href][title]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "人物卡片含“查看”文本，姓名必须取详情链接title，职务只取同卡片h5 span。",
}


def normalize_text(text: str) -> str:
    """确定性清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导班子卡片顺序提取姓名、职务和真实详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for item in soup.select("ul#lingdaobz > li"):
        duty_node = item.select_one("h5 span")
        link = item.select_one("p.text-right a[href][title]")
        if duty_node is None or link is None:
            continue

        name = normalize_text(str(link.get("title") or ""))
        duty_raw = normalize_text(duty_node.get_text(" ", strip=True))
        duty = duty_raw.rstrip(":：").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or not duty:
            continue

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, str(link.get("href") or "")),
                "evidence": duty,
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
