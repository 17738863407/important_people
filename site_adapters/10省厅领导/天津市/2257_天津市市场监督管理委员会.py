from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def clean_text(value: str) -> str:
    """压缩页面排版空白，不改变职务字段语义。"""
    return " ".join((value or "").replace("\xa0", " ").split()).strip()


def clean_name(value: str) -> str:
    """移除姓名字符之间的排版空白。"""
    return re.sub(r"[\s\u2000-\u200a\u3000]+", "", value or "")


def is_hidden(node: Tag) -> bool:
    """排除节点及祖先上明确隐藏的备用 DOM。"""
    current: Tag | None = node
    while current is not None:
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        style = re.sub(r"\s+", "", str(current.get("style", "")).lower())
        if "display:none" in style or "visibility:hidden" in style:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def same_origin(reference_url: str, candidate_url: str) -> bool:
    """检查详情页是否仍位于权威入口同源站点。"""
    reference = urlsplit(reference_url)
    candidate = urlsplit(candidate_url)
    return (reference.scheme, reference.netloc) == (candidate.scheme, candidate.netloc)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按目录顺序抓取当前领导，并逐详情验证姓名和职务字段。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one("div.content.fr ul.news_list")
    if region is None:
        raise RuntimeError("未找到领导信息目录")

    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for anchor in region.select(":scope > li > a[href]"):
        if is_hidden(anchor):
            continue
        name = clean_name(anchor.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name) or name in seen_names:
            continue

        detail_url = urljoin(final_url, str(anchor.get("href", "")))
        detail_path = urlsplit(detail_url).path
        if not same_origin(final_url, detail_url) or not re.fullmatch(
            r"/tjsscjdglwyh_52651/zwgk/ldxx/\d{6}/t\d{8}_\d+\.html",
            detail_path,
        ):
            raise RuntimeError(f"{name}详情路径不符合领导信息栏目结构")

        fetch_result = fetch_by_raw_requests(detail_url, timeout=30)
        detail_soup = BeautifulSoup(fetch_result.html, "lxml")
        detail_region = detail_soup.select_one(".content_page .part_con")
        if detail_region is None:
            raise RuntimeError(f"{name}详情页缺少人物内容区域")
        detail_name_node = detail_region.select_one(".name > font")
        info_node = detail_region.select_one(".info")
        if detail_name_node is None or info_node is None:
            raise RuntimeError(f"{name}详情页缺少姓名或职务字段")
        detail_name = clean_name(detail_name_node.get_text(" ", strip=True))
        if detail_name != name:
            raise RuntimeError(f"{name}目录姓名与详情姓名不一致：{detail_name or '空'}")

        info_text = clean_text(info_node.get_text(" ", strip=True)).replace(":", "：")
        if not info_text.startswith("职务："):
            raise RuntimeError(f"{name}详情页职务字段标签不一致")
        duty = info_text.removeprefix("职务：").strip()
        if not duty:
            raise RuntimeError(f"{name}详情页职务字段为空")

        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": fetch_result.final_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_tianjin_market_leader_directory_v1",
            }
        )
    return records


PAGE_RULE = {
    "rule_id": "2257",
    "page_type": "人物目录详情页",
    "structure_group": "tianjin_market_leader_directory",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_tianjin_market_leader_directory_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "div.content.fr ul.news_list",
    "name_selector": ":scope > li > a[href]",
    "duty_selector": ".content_page .part_con .info",
    "detail_link_selector": ":scope > li > a[href]",
    "risk_flag": "二字姓名含排版空格，个别详情姓名后含拼音；仅取姓名 font 与明确职务字段",
    "confidence": "high",
}


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
