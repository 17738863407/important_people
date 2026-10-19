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
    "rule_id": "3458",
    "domain": "zyygl.gansu.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "gansu_traditional_medicine_leader_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "browser_dom",
    "parser": "page_inline_gansu_traditional_medicine_leader_links_v1",
    "leader_region_selector": "body",
    "leader_link_selector": "a[href*='/ldzc_list.shtml']",
    "detail_strategy": {
        "required": False,
        "mode": "current_leader_links",
    },
    "risk_flag": "普通HTTP返回412防护页；领导链接文本为姓名和职务组合字段，须限定ldzc_list人物路径",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def split_name_duty(value: str) -> tuple[str, str]:
    text = clean_text(value)
    match = re.fullmatch(r"([\u4e00-\u9fff·\s]{2,10})\s+(.+)", text)
    if match is None:
        return "", ""
    name = re.sub(r"\s+", "", match.group(1))
    return name, match.group(2).strip("：:，,。.；;")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按渲染后领导之窗链接顺序解析姓名、职务和人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(str(page_rule["leader_link_selector"])):
        name, evidence = split_name_duty(link.get_text(" ", strip=True))
        if not name or not evidence or name in seen:
            continue
        evidence = re.sub(r"[（(]\s*兼\s*[）)]", "", evidence).strip(" ，,；;")
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
            }
        )
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
