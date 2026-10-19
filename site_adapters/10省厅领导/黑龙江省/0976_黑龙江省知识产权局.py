from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0976",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "div.listright div.jgld_list",
    "row_selector": "div.listright div.jgld_list > ul > li",
    "name_selector": ".jgld_info h3.name",
    "duty_selector": ".jgld_info > .zw中的完整现任句",
    "detail_link_selector": ".jgld_info > .more a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "简介.zw混合人口学信息和现任句，必须在当前卡片内只取完整现任句；分工.fg不得进入职务依据。",
}


def normalize_text(text: str) -> str:
    """仅压缩卡片字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def normalize_name(text: str) -> str:
    """去除姓名中的排版空格。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(text or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片顺序提取姓名、完整现任句和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for card in soup.select("div.listright div.jgld_list > ul > li"):
        name_node = card.select_one(".jgld_info h3.name")
        profile_node = card.select_one(".jgld_info > .zw")
        detail_link = card.select_one(".jgld_info > .more a[href]")
        name = normalize_name(name_node.get_text(" ", strip=True) if name_node is not None else "")
        profile = normalize_text(profile_node.get_text(" ", strip=True) if profile_node is not None else "")
        current_match = re.search(r"现任[^。]*。", profile)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or current_match is None:
            continue
        evidence = current_match.group(0)
        duty = evidence.removeprefix("现任").removesuffix("。")

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
