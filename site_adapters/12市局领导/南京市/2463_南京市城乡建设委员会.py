from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2463",
    "page_type": "人物列表完整页",
    "structure_group": "nanjing_construction_iframe_profile_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "iframe嵌入",
    "fetch_mode": "requests",
    "extract_mode": "custom_parse_page",
    "parser": "nanjing_construction_iframe_profile_paragraphs_v1",
    "leader_region_selector": "iframe#dataList[src] -> div#heightbox2",
    "name_selector": "div#heightbox2 p",
    "duty_selector": "div#heightbox2 p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口仅含机构概况iframe；frame正文还包含机构职责和工作分工，须限定简介首段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅合并网页排版空白。"""
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """在线读取机构概况iframe，并按简介段原序抽取姓名和职务。"""
    from bs4 import BeautifulSoup

    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    entry_soup = BeautifulSoup(html, "html.parser")
    frames = entry_soup.select("iframe#dataList[src]")
    if len(frames) != 1:
        raise RuntimeError(f"机构概况iframe命中数量异常：{len(frames)}")
    entry_url = final_url or page_rule["url"]
    frame_url = urljoin(entry_url, str(frames[0].get("src") or ""))
    entry_parts = urlsplit(entry_url)
    frame_parts = urlsplit(frame_url)
    if frame_parts.netloc.lower() != entry_parts.netloc.lower():
        raise RuntimeError("机构概况iframe不是同域页面")
    if not re.fullmatch(
        r"/njscxjswyh/xxgkzl/jggk/index_\d+\.html", frame_parts.path
    ):
        raise RuntimeError(f"机构概况iframe路径异常：{frame_parts.path}")

    frame_result = fetch_html_with_strategy(frame_url, strategy="requests", timeout=60)
    frame_soup = BeautifulSoup(frame_result.html, "html.parser")
    regions = frame_soup.select("div#heightbox2")
    if len(regions) != 1:
        raise RuntimeError(f"机构概况正文命中数量异常：{len(regions)}")

    organization = str(page_rule["organization"])
    profile_pattern = re.compile(
        rf"^(?P<name>[\u3400-\u9fff·]{{2,10}})，\s*{re.escape(organization)}"
        r"(?P<duty>.+?)(?=，(?:男|女)，)"
    )
    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in regions[0].select("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        match = profile_pattern.match(text)
        if not match:
            continue
        name = match.group("name")
        evidence = _clean_text(match.group("duty")).strip("，。； ")
        if name in seen_names:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=organization,
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )

    if not records:
        raise RuntimeError("机构概况iframe中未找到可核验的人物简介段")
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
