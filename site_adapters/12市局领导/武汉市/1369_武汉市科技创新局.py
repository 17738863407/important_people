from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1369",
    "page_type": "人物列表完整页",
    "structure_group": "wuhan_science_grouped_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "wuhan_science_grouped_leader_cards_v2",
    "leader_region_selector": ".list_news",
    "name_selector": ".leader-item a[href] p",
    "duty_selector": ".leader-item .leader-job-name h2",
    "detail_link_selector": ".leader-item a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_link_only",
        "detail_link_selector": ".leader-item a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "原始响应含完整职务分组；HTTP头声明ISO-8859-1但正文为UTF-8",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性合并页面排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_entry_soup(html: str) -> BeautifulSoup:
    """必要时严格回转错误HTTP字符集造成的UTF-8乱码。"""
    soup = BeautifulSoup(html or "", "html.parser")
    fields = soup.select(".list_news .leader-item a[href] p")
    names = [re.sub(r"\s+", "", clean_text(field.get_text(" ", strip=True))) for field in fields]
    if fields and not any(re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) for name in names):
        try:
            repaired_html = (html or "").encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
        soup = BeautifulSoup(repaired_html, "html.parser")
    return soup


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按职务分组及组内卡片DOM顺序提取姓名、职务和详情链接。"""
    from crawler_core.models import PersonRecord

    soup = parse_entry_soup(html)
    regions = soup.select(".list_news")
    if len(regions) != 1:
        raise RuntimeError(f"领导区域数量异常：{len(regions)}")

    groups = regions[0].select(".leader-item")
    if not groups:
        raise RuntimeError("领导区域没有可验证职务分组")

    records: list[object] = []
    seen_names: set[str] = set()
    seen_links: set[str] = set()
    for group in groups:
        duty_node = group.select_one(".leader-job-name h2")
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        cards = group.select("a[href]")
        if not evidence and not cards:
            # 当前页面保留了仅含已注释历史人物的空分组，不属于可见领导数据。
            continue
        if not evidence or not cards:
            raise RuntimeError(f"领导职务分组标题或卡片为空：{evidence}")
        for card in cards:
            name_node = card.select_one("p")
            name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
            detail_url = urljoin(final_url, card.get("href", "").strip())
            parts = urlsplit(detail_url)
            if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None:
                raise RuntimeError(f"领导卡片姓名异常：{name}")
            if parts.scheme not in {"http", "https"} or not parts.netloc or detail_url == final_url:
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
        raise RuntimeError("领导信息页没有可验证人物卡片")
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
