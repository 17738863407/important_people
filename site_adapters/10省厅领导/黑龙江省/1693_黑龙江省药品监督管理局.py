from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1693",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".jgld_list",
    "row_selector": ".jgld_list > ul > li",
    "name_selector": ".jgld_info h3.name",
    "duty_selector": ".jgld_info > div.zw:not(.jl)",
    "detail_link_selector": ".jgld_info > a.ckxq[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "卡片同时含明确职务、分工和简历摘要，依据必须只取非.jl的职务div，禁止使用宽泛a[href]或拼接姓名。",
}


def normalize_text(text: str) -> str:
    """仅压缩卡片字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def normalize_name(text: str) -> str:
    """去除姓名中的排版空格。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(text or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按机构领导卡片顺序提取姓名、原始职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for card in soup.select(".jgld_list > ul > li"):
        name_node = card.select_one(".jgld_info h3.name")
        duty_node = card.select_one(".jgld_info > div.zw:not(.jl)")
        detail_link = card.select_one(".jgld_info > a.ckxq[href]")
        name = normalize_name(name_node.get_text(" ", strip=True) if name_node is not None else "")
        raw_duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node is not None else "")
        duty = re.sub(r"^职务\s*[：:]\s*", "", raw_duty)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": (
                    urljoin(final_url, str(detail_link.get("href") or ""))
                    if detail_link is not None
                    else ""
                ),
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
