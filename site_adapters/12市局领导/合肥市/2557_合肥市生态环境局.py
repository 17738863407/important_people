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


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(
    html: str,
    final_url: str,
    _page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按领导目录顺序读取人物详情页首个“姓名：职务”段落。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.xxgk-table-list")
    if table is None:
        raise ValueError("未找到机构领导表格 table.xxgk-table-list")

    if not final_url:
        raise ValueError("在线采集结果缺少最终入口网址")
    base_url = final_url
    detail_urls: list[str] = []
    seen_urls: set[str] = set()
    for link in table.select("tbody > tr.mc td.title-td > a.title[href]"):
        href = str(link.get("href") or "").strip()
        if not href or href.lower().startswith(("javascript:", "mailto:", "#")):
            continue
        detail_url = urljoin(base_url, href)
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        detail_urls.append(detail_url)

    if not detail_urls:
        raise ValueError("机构领导表格未发现有效人物详情链接")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=table.xxgk-table-list；"
        "detail=tbody > tr.mc td.title-td > a.title[href]；"
        "name/duty=#zoom.j-fontContent直接子p首个姓名：职务段落；collector=playwright"
    )
    for detail_url in detail_urls:
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="playwright")
        except Exception as error:
            raise RuntimeError(f"人物详情页采集失败 {detail_url}：{error}") from error

        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        content = detail_soup.select_one("#zoom.j-fontContent")
        if content is None:
            raise ValueError(f"详情页未找到 #zoom.j-fontContent：{detail_url}")

        name = ""
        duty = ""
        evidence = ""
        for paragraph in content.find_all("p", recursive=False):
            paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
            match = re.fullmatch(r"([\u4e00-\u9fff·]{2,8})\s*[:：]\s*(.+)", paragraph_text)
            if match is None:
                continue
            name = match.group(1).replace(" ", "")
            duty = clean_text(match.group(2))
            evidence = paragraph_text
            break
        if not name or not duty:
            raise ValueError(f"详情页首段未找到有效“姓名：职务”结构：{detail_url}")
        if name in seen_names:
            raise ValueError(f"机构领导目录出现重复姓名：{name}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
            "evidence": duty,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": "page_inline_hefei_environment_detail_heading_v1",
                "selector_summary": selector_summary,
            }
        )

    return rows


PAGE_RULE = {
    "rule_id": "2557",
    "page_type": "人物目录详情页",
    "structure_group": "hefei_public_leader_detail_heading",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "list_to_detail",
    "collector": "browser_dom",
    "parser": "page_inline_hefei_environment_detail_heading_v1",
    "leader_region_selector": "table.xxgk-table-list",
    "name_selector": "#zoom.j-fontContent > p[文本结构=姓名：职务]",
    "duty_selector": "#zoom.j-fontContent > p[文本结构=姓名：职务]",
    "detail_link_selector": "tbody > tr.mc td.title-td > a.title[href]",
    "detail_strategy": {"required": False, "mode": "inline_detail_fetch"},
    "risk_flag": "普通HTTP返回521；已核验general环境Playwright可稳定取得8人目录及详情页姓名职务段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "table.xxgk-table-list",
            "name_selector": "#zoom.j-fontContent > p[文本结构=姓名：职务]",
            "duty_selector": "#zoom.j-fontContent > p[文本结构=姓名：职务]",
            "detail_link_selector": "tbody > tr.mc td.title-td > a.title[href]",
        },
        "api": {
            "enabled": False,
            "reason": "当前领导目录及详情页均由浏览器渲染DOM稳定提供，普通HTTP受521防护拦截",
        },
        "migration": {
            "source": "failed_script_v3_task7",
            "verified_status": "online_verified_20260808",
            "behavior_changed": True,
        },
    },
}


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
