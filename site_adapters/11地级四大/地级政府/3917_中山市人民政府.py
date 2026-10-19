from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3917",
    "page_type": "政务公开首页领导卡片",
    "structure_group": "zhongshan_government_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_zhongshan_government_cards_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".zw_ld",
    "name_selector": "同href可见姓名链接",
    "duty_selector": "a.leader-pic img[title]去除当前姓名后缀",
    "detail_link_selector": "a.leader-pic[href]",
    "risk_flag": "页面含注释掉的历史卡片；BeautifulSoup DOM解析须排除注释内容",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名中的排版空白及市长展示括注。"""
    name = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()
    return re.sub(r"[（(]市长[）)]$", "", name).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按可见领导图片卡片顺序提取当前姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    region = soup.select_one(".zw_ld")
    if region is None:
        raise RuntimeError("未定位到领导之窗区域")

    names_by_url: dict[str, list[str]] = {}
    for link in region.select("a[href]"):
        href = clean_text(link.get("href"))
        detail_url = urljoin(base_url, href) if href else ""
        name = clean_name(link.get_text(" ", strip=True))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            names_by_url.setdefault(detail_url, []).append(name)

    rows: list[dict] = []
    seen_names: set[str] = set()
    for card_link in region.select("a.leader-pic[href]"):
        image = card_link.select_one("img[title]")
        href = clean_text(card_link.get("href"))
        detail_url = urljoin(base_url, href) if href else ""
        if image is None or urlparse(detail_url).scheme not in {"http", "https"}:
            continue
        title = clean_text(image.get("title"))
        name = next((item for item in names_by_url.get(detail_url, []) if title.endswith(item)), "")
        if not name or name in seen_names:
            continue
        evidence = clean_text(title[: -len(name)])
        if not evidence:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": ".zw_ld a.leader-pic及同href可见姓名链接",
            }
        )

    if not rows:
        raise RuntimeError("领导之窗卡片未提取到有效人物")
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
