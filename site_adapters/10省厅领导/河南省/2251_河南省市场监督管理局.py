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
    "rule_id": "2251",
    "page_type": "人物目录详情页",
    "structure_group": "henan_market_leader_details_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "requests",
    "parser": "inline_parse_page",
    "leader_region_selector": ".ldList li",
    "name_selector": ".ldList li p",
    "duty_selector": ".conBox",
    "detail_link_selector": ".ldList li a[href]",
    "content_scope": {
        "include_selectors": [".ldList", ".conBox"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_raw_http_detail",
        "detail_content_selector": ".conBox",
    },
    "risk_flag": "入口仅首人显示职务，必须逐详情在当前人物正文提取完整现任句并排除分管、联系和历史履历",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_text(value: str) -> str:
    """只压缩页面排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def normalize_name(value: str) -> str:
    """删除姓名节点内部的纯排版空白。"""
    return re.sub(r"\s+", "", normalize_text(value))


def parse_detail(html: str, expected_name: str, detail_url: str) -> dict[str, str]:
    """在当前人物详情正文中提取完整“现任……”原句。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".conBox")
    if content is None:
        raise ValueError(f"人物详情页缺少正文容器：{detail_url}")
    content_text = normalize_text(content.get_text(" ", strip=True))
    evidence_match = re.search(r"现任[^。]*。", content_text)
    if evidence_match is None:
        raise ValueError(f"人物详情正文缺少现任职务原句：{detail_url}")
    prefix = normalize_name(content_text[: evidence_match.start()])
    if expected_name not in prefix:
        raise ValueError(f"人物详情正文无法回指入口姓名：{expected_name}，页面={detail_url}")
    evidence = re.sub(
        r"^现任(?:职务)?\s*[：:]?\s*",
        "",
        normalize_text(evidence_match.group(0)),
    ).rstrip("。；; ")
    return {
        "name": expected_name,
        "duty": evidence,
        "evidence": evidence,
        "detail_url": detail_url,
    }


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口卡片顺序动态抓取并解析全部当前领导详情。"""
    del page_rule
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".ldList li")
    if not cards:
        raise ValueError("机构领导入口未发现人物卡片")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for card in cards:
        name_node = card.select_one("p")
        link = card.select_one("a[href]")
        if name_node is None or link is None:
            raise ValueError("人物卡片缺少姓名或详情链接")
        name = normalize_name(name_node.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href") or "").strip())
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            raise ValueError(f"人物卡片姓名格式异常：{name!r}")
        if name in seen_names or detail_url in seen_urls:
            continue
        result = fetch_by_raw_requests(detail_url)
        rows.append(parse_detail(result.html, name, detail_url))
        seen_names.add(name)
        seen_urls.add(detail_url)
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
