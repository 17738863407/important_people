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
    "rule_id": "1298",
    "page_type": "人物列表完整页",
    "structure_group": "leader_card_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ShaanxiPrisonLeaderCardParser_v1",
    "leader_region_selector": "a.am-u-lg-4[href]",
    "name_selector": ".w-name",
    "duty_selector": ".w-posi",
    "detail_link_selector": "a.am-u-lg-4[href]",
    "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high",
    "risk_flag": "姓名可能含全角排版空格，详情链接必须从当前卡片动态解析",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_standalone_concurrent_marker(text: str) -> str:
    """删除独立“兼”状态标记，保留实际兼任职务和其他任职语义。"""
    cleaned = re.sub(r"(?:（兼）|\(兼\)|[<＜]兼[>＞])", "", _clean_text(text))
    return re.sub(r"[，,、；;：:]\s*$", "", cleaned).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """按人物卡片顺序提取姓名、职务和独立详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a.am-u-lg-4[href]"):
        name_node = link.select_one(".w-name")
        duty_node = link.select_one(".w-posi")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = _clean_standalone_concurrent_marker(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": "",
                "detail_url": urljoin(base_url, link.get("href", "")),
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "a.am-u-lg-4[href]；姓名=.w-name；职务=.w-posi；详情=a[href]",
                "order": str(len(records) + 1),
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
