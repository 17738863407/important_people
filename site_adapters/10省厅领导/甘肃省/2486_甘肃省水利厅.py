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
    "rule_id": "2486",
    "domain": "slt.gansu.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_gansu_slt_colon_leaders_v1",
    "leader_region_selector": "body",
    "name_selector": "姓名：职务 text head",
    "duty_selector": "姓名：职务 text tail",
    "detail_link_selector": "a[href] containing 姓名：职务",
    "content_scope": {"start_anchor": "机构领导", "end_anchor": "| 网站首页", "include_selectors": ["body"], "exclude_selectors": []},
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "browser_dom",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "正文领导区按“姓名：职务”排列，部分姓名含空格",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "body",
            "name_selector": "姓名：职务 text head",
            "duty_selector": "姓名：职务 text tail",
            "detail_link_selector": "a[href] containing 姓名：职务",
            "content_scope": {"start_anchor": "机构领导", "end_anchor": "| 网站首页", "include_selectors": ["body"], "exclude_selectors": []},
        },
        "api": {"enabled": False, "reason": "在线浏览器 DOM 已包含完整领导名单"},
    },
}


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text)).strip("：:，,。.；;")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    text = normalize_space(soup.get_text(" ", strip=True))
    start = text.rfind("下载服务 机构领导")
    if start == -1:
        start = text.find("机构领导")
    end = text.find("| 网站首页", start)
    segment = text[start:end if end != -1 else len(text)]
    if "机构领导" in segment:
        segment = segment.split("机构领导", 1)[1]

    link_map: dict[str, str] = {}
    for link in soup.select("a[href]"):
        link_text = normalize_space(link.get_text(" ", strip=True))
        if "：" not in link_text:
            continue
        name = clean_name(link_text.split("：", 1)[0])
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        link_map[name] = detail_url

    rows: list[dict[str, str]] = []
    pattern = re.compile(r"(?P<name>[\u4e00-\u9fff·\s]{2,6})：(?P<duty>.*?)(?=\s+[\u4e00-\u9fff·\s]{2,6}：|$)")
    for match in pattern.finditer(segment):
        name = clean_name(match.group("name"))
        duty = normalize_space(match.group("duty")).strip("：:，,。.；;")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not duty or any(row["name"] == name for row in rows):
            continue
        if not re.search(r"党组|厅长|巡视员|总工程师|总规划师|纪检监察", duty):
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": link_map.get(name, ""),
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=机构领导文本；fields=姓名：职务；detail_chain=0",
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
