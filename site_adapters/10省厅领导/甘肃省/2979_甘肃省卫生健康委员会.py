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
    "rule_id": "2979",
    "domain": "wsjk.gansu.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "gansu_health_leader_intro_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "browser_dom",
    "parser": "page_inline_gansu_health_leader_intro_links_v1",
    "leader_region_selector": ".m_new_section.main",
    "leader_link_selector": "a[href] > em",
    "name_selector": "span",
    "detail_strategy": {
        "required": False,
        "mode": "current_leader_links",
    },
    "risk_flag": "普通HTTP返回412防护页；渲染后领导链接em内span为姓名、剩余直接文本为职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    return re.sub(r"[\s\u3000\u00a0]+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按渲染后领导简介链接顺序抽取姓名、职务和人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(str(page_rule["leader_region_selector"]))
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for em in region.select(str(page_rule["leader_link_selector"])):
        name_node = em.select_one(str(page_rule["name_selector"]))
        link = em.parent if em.parent and em.parent.name == "a" else None
        displayed_name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        name = clean_name(displayed_name)
        combined = clean_text(em.get_text(" ", strip=True))
        evidence = combined[len(displayed_name) :].strip(" ：:，,。.；;") if combined.startswith(displayed_name) else ""
        evidence = evidence.replace("（兼）", "").replace("(兼)", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(final_url, str(link.get("href") or "")) if link else "",
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
