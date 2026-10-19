from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3886",
    "page_type": "多业务分组人物目录详情页",
    "structure_group": "suqian_government_tab_details_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_suqian_government_tab_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".infoTab .bd > ul.nameList.emp1",
    "name_selector": "li > a[href]",
    "duty_selector": ".ldzcInfoLeftl > p",
    "detail_link_selector": "li > a[href]",
    "detail_timeout_seconds": 30,
    "risk_flag": "同页含市委、人大、政府、政协四套名单，仅第三套emp1为市政府分组",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩页面排版空白，不改变职务字段语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """仅删除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """只按市政府页签名单顺序逐一获取详情页明确职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到领导之窗中的市政府名单分组")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for link in region.select("li > a[href]"):
        expected_name = clean_name(link.get("title") or link.get_text(" ", strip=True))
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", expected_name) or not detail_url:
            continue

        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy="raw_http",
            timeout=int(page_rule["detail_timeout_seconds"]),
        )
        detail_soup = BeautifulSoup(detail_result.html, "lxml")
        info = detail_soup.select_one(".ldzcInfoLeftl")
        name_node = info.find("h4", recursive=False) if info is not None else None
        duty_node = info.find("p", recursive=False) if info is not None else None
        detail_name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if detail_name != expected_name or not duty:
            raise RuntimeError(
                f"人物详情姓名或职务字段不完整：{expected_name} / {detail_result.final_url}"
            )
        if detail_name in seen_names:
            continue

        seen_names.add(detail_name)
        rows.append(
            {
                "name": detail_name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "市政府.nameList.emp1人物链接；详情.ldzcInfoLeftl直属h4姓名和p职务",
            }
        )

    if not rows:
        raise RuntimeError("市政府名单详情页未提取到有效人物")
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
