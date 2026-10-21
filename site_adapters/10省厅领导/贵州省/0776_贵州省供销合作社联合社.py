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


def clean_text(value: str) -> str:
    """压缩网页文本空白，不改变简介原句语义。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def clean_evidence(value: str) -> str:
    """清理简介句的固定引导词与纯句末标点，保留可回指的职务原文。"""
    return clean_text(value).removeprefix("现任").rstrip("。")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按卡片DOM顺序提取姓名、简介中的完整现任句和独立详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, card in enumerate(soup.select(".ldzc_box .bmgk_con"), start=1):
        link = card.select_one(".bmgk_text > a[href][title]") or card.select_one("a[href][title]")
        name = clean_text(str(link.get("title") if link else "")).replace(" ", "")
        intro_node = card.select_one("p.bmgk_s2")
        intro = clean_text(intro_node.get_text(" ", strip=True) if intro_node else "")
        duty_match = re.search(r"现任[^。]*。", intro)
        evidence = clean_evidence(duty_match.group(0)) if duty_match else ""
        href = str(link.get("href") if link else "")
        detail_url = urljoin(final_url, href) if href else ""
        if name in seen or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "source_order": str(source_order),
                "confidence": "high" if evidence else "medium",
                "parser": "page_inline_guizhou_gxs_leader_card_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0776",
    "page_type": "多人物详情合并页",
    "structure_group": "贵州供销社领导卡片简介",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_guizhou_gxs_leader_card_v2",
    "leader_region_selector": ".ldzc_box .bmgk_con",
    "name_selector": ".bmgk_text > a[title]",
    "duty_selector": "p.bmgk_s2内完整现任句",
    "detail_link_selector": ".bmgk_text > a[href][title]",
    "detail_strategy": {
        "required": False,
        "mode": "card_link_only",
        "detail_collector_type": "none",
    },
    "risk_flag": "职务节点由页面脚本生成，改取同一卡片简介内可回指的完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
