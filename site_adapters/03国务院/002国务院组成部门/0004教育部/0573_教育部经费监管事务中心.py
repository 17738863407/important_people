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
    "rule_id": "0573",
    "page_type": "人物列表完整页",
    "structure_group": "中心领导详情链接卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "FsacLeaderCardLinksParser_v2",
    "leader_region_selector": ".detail_right .list_right_img, .detail_right .list_right_img1",
    "name_selector": "a[href]文本末尾姓名",
    "duty_selector": "a[href]完整文本",
    "detail_link_selector": ".detail_right .list_right_img a[href], .detail_right .list_right_img1 a[href]",
    "detail_strategy": {"required": False, "mode": "list_card_link"},
    "risk_flag": "普通HTTP受412限制，需浏览器取得当前卡片；详情链接必须从人物卡片href动态提取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按中心领导卡片DOM顺序抽取链接文本和独立详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    selector = ".detail_right .list_right_img a[href], .detail_right .list_right_img1 a[href]"
    for link in soup.select(selector):
        evidence = _clean_text(link.get_text(" ", strip=True))
        matched = re.fullmatch(r"(.+?)\s+([\u4e00-\u9fff·]{2,5})", evidence)
        if not matched:
            continue
        name = matched.group(2)
        if name in seen_names:
            continue
        duty = _clean_text(matched.group(1))
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, link.get("href", "")),
                "parser": PAGE_RULE["parser"],
                "selector_summary": "detail_right内list_right_img/list_right_img1人物链接；文本末尾姓名；当前卡片href详情；按DOM顺序",
            }
        )
    if not records:
        raise RuntimeError("中心领导详情链接卡片未解析到人物记录")
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
