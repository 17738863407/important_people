from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0663",
    "page_type": "人物目录详情页",
    "structure_group": "gansu_gdb_leader_details_v1",
    "reuse_scope": "single_page",
    "load_mode": "Chrome渲染DOM",
    "fetch_mode": "chrome",
    "extract_mode": "list_to_detail",
    "collector": "chrome_cdp",
    "parser": "inline_parse_page",
    "leader_region_selector": ".scroll_main .scroll_cont",
    "name_selector": ".center_RF.margin-t20 h1",
    "duty_selector": ".center_RF.margin-t20 p",
    "detail_link_selector": ".scroll_cont a[href]",
    "content_scope": {
        "include_selectors": [".scroll_main .scroll_cont"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_chrome_detail",
        "detail_content_selector": ".center_RF.margin-t20",
    },
    "risk_flag": "列表标题被省略号截断，必须从动态发现的一一对应详情页提取姓名与领导简介职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_text(value: str) -> str:
    """只压缩页面排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def clean_duty_evidence(value: str) -> str:
    """删除独立兼任状态标记，保留具体兼任职务。"""
    return re.sub(r"(?:<\s*兼\s*>|[（(]\s*兼\s*[）)])", "", normalize_text(value)).strip()


def discover_detail_urls(html: str, final_url: str) -> list[str]:
    """在机构领导正文中按DOM顺序发现唯一人物详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".scroll_main .scroll_cont")
    if region is None:
        raise ValueError("未找到机构领导正文容器")

    entry_path = urlparse(final_url).path
    section_path = entry_path.rsplit("/", 1)[0] + "/"
    detail_pattern = re.compile(rf"^{re.escape(section_path)}\d{{6}}/\d+\.shtml$")
    urls: list[str] = []
    for anchor in region.select("a[href]"):
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        if not detail_pattern.fullmatch(urlparse(detail_url).path):
            continue
        if detail_url not in urls:
            urls.append(detail_url)
    if not urls:
        raise ValueError("机构领导正文未发现人物详情链接")
    return urls


def parse_detail(html: str, detail_url: str) -> dict[str, str]:
    """从一一对应详情页提取标题末尾姓名和“领导简介”后的原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".center_RF.margin-t20")
    title_node = region.select_one("h1") if region else None
    if region is None or title_node is None:
        raise ValueError(f"人物详情页缺少正文或标题：{detail_url}")

    raw_duty = ""
    for paragraph in region.select("p"):
        if normalize_text(paragraph.get_text(" ", strip=True)) != "领导简介":
            continue
        sibling = paragraph.find_next_sibling("p")
        if isinstance(sibling, Tag):
            raw_duty = normalize_text(sibling.get_text(" ", strip=True))
        break
    if not raw_duty:
        raise ValueError(f"人物详情页缺少领导简介职务：{detail_url}")

    title = normalize_text(title_node.get_text(" ", strip=True))
    if not title.startswith(raw_duty):
        raise ValueError(f"详情标题与领导简介职务不一致：{detail_url}")
    name = re.sub(r"\s+", "", title[len(raw_duty) :])
    if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
        raise ValueError(f"详情标题末尾姓名格式异常：{detail_url}，值={name!r}")
    duty = clean_duty_evidence(raw_duty)

    return {
        "name": name,
        "duty": duty,
        "evidence": duty,
        "detail_url": detail_url,
    }


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按列表原序逐页获取并解析当前机构领导。"""
    del page_rule
    from crawler_core.fetcher import fetch_by_chrome_debug

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for detail_url in discover_detail_urls(html, final_url):
        result = fetch_by_chrome_debug(detail_url)
        row = parse_detail(result.html, result.final_url)
        name = row["name"]
        if name in seen_names:
            raise ValueError(f"人物详情页出现重复姓名：{name}")
        seen_names.add(name)
        rows.append(row)
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
