from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0970",
    "page_type": "人物列表完整页",
    "structure_group": "haikou_housing_name_bracket_duty_links",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".gkpd-ld, .gkpd-ldd3",
    "name_selector": ".gkpd-ld与.gkpd-ldd3人物链接文本括号前",
    "duty_selector": ".gkpd-ld与.gkpd-ldd3人物链接文本方括号内",
    "detail_link_selector": ".gkpd-ld a.leaidx[href*='/ldxx/'], .gkpd-ldd3 a.leaidx[href*='/ldxx/']",
    "content_scope": {
        "start_anchor": "市住建局领导",
        "end_anchor": "机构概况",
        "include_selectors": [".gkpd-ld", ".gkpd-ldd3"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "links_from_listing",
        "detail_link_selector": ".gkpd-ld a.leaidx[href*='/ldxx/'], .gkpd-ldd3 a.leaidx[href*='/ldxx/']",
        "max_detail_links": 50,
    },
    "risk_flag": "领导列表链接文本为姓名加方括号原始职务，保留原标点且只接受领导容器内真实详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def fetch_complete_listing(url: str) -> str:
    """以站点可稳定返回完整双容器的原始HTTP通道读取当前入口。"""
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        encoding = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(encoding, errors="replace")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(fetch_complete_listing(final_url), "html.parser")
    rows: list[dict[str, str]] = []
    pattern = re.compile(r"^(?P<name>[\u3400-\u9fff·]{2,12})\[(?P<duty>[^\]]+)\]$")
    selector = (
        ".gkpd-ld a.leaidx[href*='/ldxx/'], "
        ".gkpd-ldd3 a.leaidx[href*='/ldxx/']"
    )
    for link in soup.select(selector):
        text = clean_text(link.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        href = str(link.get("href") or "").strip()
        if not match or not href:
            continue
        duty = match.group("duty")
        rows.append(
            {
                "name": match.group("name"),
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, href),
                "selector_summary": ".gkpd-ld领导链接姓名及方括号原始职务",
            }
        )
    if not rows:
        raise ValueError("市住建局领导容器未发现姓名加方括号职务的有效人物链接")
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
