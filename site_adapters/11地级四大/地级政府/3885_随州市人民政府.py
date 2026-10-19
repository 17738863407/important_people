from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3885",
    "page_type": "人物卡片列表页",
    "structure_group": "suizhou_government_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_suizhou_government_cards_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".mayor-r, .leader-other",
    "name_selector": ".mayor-name a.name, .leader-other-c p.h4",
    "duty_selector": ".mayor-name .post, .leader-other-c > span",
    "detail_link_selector": ".mayor-name a.name[href], .leader-other-img a[href]",
    "risk_flag": "首位市长与其余领导卡片结构不同，详情链接须在同一人物卡片内配对",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩卡片排版空白，不改变职务字段语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """先提取首位市长，再按其余人物卡片顺序提取领导信息。"""
    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()

    def append_row(name_value: object, duty_value: object, href_value: object) -> None:
        name = clean_name(name_value)
        duty = clean_text(duty_value)
        href = str(href_value or "").strip()
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not duty:
            return
        if name in seen_names or not detail_url:
            return
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "首位市长块或同一其余领导卡片内的姓名、职务和头像链接",
            }
        )

    mayor = soup.select_one(".mayor-r")
    if mayor is not None:
        mayor_link = mayor.select_one(".mayor-name a.name[href]")
        mayor_duty = mayor.select_one(".mayor-name .post")
        append_row(
            mayor_link.get_text(" ", strip=True) if mayor_link else "",
            mayor_duty.get_text(" ", strip=True) if mayor_duty else "",
            mayor_link.get("href") if mayor_link else "",
        )

    for card in soup.select(".leader-other .layui-col-xs3"):
        name_node = card.select_one(".leader-other-c p.h4")
        duty_node = card.select_one(".leader-other-c > span")
        detail_link = card.select_one(".leader-other-img a[href]")
        append_row(
            name_node.get_text(" ", strip=True) if name_node else "",
            duty_node.get_text(" ", strip=True) if duty_node else "",
            detail_link.get("href") if detail_link else "",
        )

    if not rows:
        raise RuntimeError("市政府领导人物卡片未提取到有效人物")
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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
