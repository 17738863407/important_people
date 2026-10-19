from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0989",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".con.xrld",
    "row_selector": ".con.xrld a[href]",
    "name_selector": ".inf > p",
    "duty_selector": ".inf > span",
    "detail_link_selector": ".con.xrld a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "现任领导卡片包含机构全称及换行职务，必须保留原始机构前缀并禁止进入详情页抓取领导动态作为职务。",
}


def normalize_text(text: str) -> str:
    """压缩领导卡片中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def normalize_name(text: str) -> str:
    """去除姓名中的排版空格。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(text or "")).strip()


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按现任领导卡片顺序提取页面直接给出的姓名与完整职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for link in soup.select(".con.xrld a[href]"):
        href = str(link.get("href") or "")
        if "/About/index/cid/28/lid/37/id/" not in href:
            continue
        name_node = link.select_one(".inf > p")
        duty_node = link.select_one(".inf > span")
        if name_node is None or duty_node is None:
            continue

        raw_name = normalize_text(name_node.get_text(" ", strip=True))
        name = normalize_name(raw_name)
        duty = normalize_text(duty_node.get_text(" ", strip=True)).strip("，,。；;、 ")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, href),
                "evidence": f"{raw_name} {duty}",
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
