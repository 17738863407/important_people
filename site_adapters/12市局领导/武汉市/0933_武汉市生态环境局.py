from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0933",
    "page_type": "人物列表完整页",
    "structure_group": "wuhan_ecology_duty_name_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wuhan_ecology_duty_name_cards_v2",
    "leader_region_selector": "div.leader.leaders, ul.leader.h > li.mb20",
    "name_selector": "h4中末个冒号后姓名",
    "duty_selector": "h4中末个冒号前原始职务",
    "detail_link_selector": "h4父级a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_link_only",
        "detail_link_selector": "h4父级a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "首人使用置顶div卡片，其余人物使用ul内li卡片；卡片包含工作分工和多个重复详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性合并卡片标题文本空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按置顶卡片和普通卡片DOM顺序提取职务、姓名与详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    cards: list[Tag] = []
    featured = soup.select_one("div.leader.leaders")
    if featured is not None:
        cards.append(featured)
    cards.extend(soup.select("ul.leader.h > li.mb20"))

    records: list[object] = []
    seen_names: set[str] = set()
    seen_links: set[str] = set()
    for card in cards:
        heading = card.select_one("h4")
        title = clean_text(heading.get_text(" ", strip=True) if heading else "")
        if "：" not in title and ":" not in title:
            raise RuntimeError(f"领导卡片标题缺少职务姓名分隔符：{title}")
        evidence, name = re.split(r"[：:]", title, maxsplit=1)
        evidence = clean_text(evidence)
        name = re.sub(r"\s+", "", clean_text(name))
        link = heading.find_parent("a", href=True) if heading else None
        detail_url = urljoin(final_url, link.get("href", "").strip() if link else "")
        parts = urlsplit(detail_url)
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None or not evidence:
            raise RuntimeError(f"领导卡片姓名或职务异常：{name} {evidence}")
        if link is None or parts.scheme not in {"http", "https"} or not parts.netloc or detail_url == final_url:
            raise RuntimeError(f"领导卡片详情链接异常：{name} {detail_url}")
        if name in seen_names or detail_url in seen_links:
            raise RuntimeError(f"领导卡片姓名或链接重复：{name} {detail_url}")
        seen_names.add(name)
        seen_links.add(detail_url)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导信息区域没有可验证人物卡片")
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
