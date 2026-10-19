from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """清除排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按市院领导卡片原序提取可见姓名、职务及 onclick 人物链接。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".fd-content-main .fd-syld-ul")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    candidates: list[tuple[object, object, object]] = []
    if region is not None:
        for card in region.select(":scope > a > li"):
            candidates.append((card.select_one(".fd-description h4"), card.select_one(".fd-description h5"), card.parent))
    else:
        home_region = soup.select_one(".fd-syld-box")
        if home_region is None:
            raise RuntimeError("未找到市院领导详情卡片或首页市院领导区域")
        candidates.append(
            (
                home_region.select_one(".fd-syld-main h4"),
                home_region.select_one(".fd-syld-main .fd-swiper-main-zw"),
                home_region.select_one(".fd-syld-main h4"),
            )
        )
        for card in home_region.select(".fd-swiper-syld-list > li"):
            candidates.append((card.select_one("h4"), card.select_one("h5"), card.select_one("h4")))
    for name_node, duty_node, link_node in candidates:
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").strip("，,。；; ")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not duty or name in seen:
            continue
        onclick = str(link_node.get("onclick") or "") if link_node else ""
        match = re.search(r"tz\(['\"](?P<url>[^'\"]+)['\"]\)", onclick)
        detail_url = urljoin(final_url, match.group("url")) if match else ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".fd-syld-ul直属人物卡片原序；h4姓名、h5职务；父链接onclick中的人物页",
            }
        )
        seen.add(name)
    if not rows:
        raise RuntimeError("市院领导卡片未提取到目标领导")
    return rows


PAGE_RULE = {
    "rule_id": "4523",
    "domain": "www.bjjc.gov.cn",
    "page_type": "市院领导人物卡片",
    "structure_group": "beijing_procuratorate_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_beijing_procuratorate_leader_cards_v1",
    "leader_region_selector": ".fd-content-main .fd-syld-ul",
    "name_selector": ".fd-description h4",
    "duty_selector": ".fd-description h5",
    "detail_link_selector": ".fd-syld-ul > a[onclick]",
    "detail_strategy": {"required": False, "mode": "onclick_person_link"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "卡片内含display:none简介副本；只读取可见h4/h5，详情地址动态来自父链接onclick；领导区域内的检察委员会委员、专职委员等均按网页原序保留",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
