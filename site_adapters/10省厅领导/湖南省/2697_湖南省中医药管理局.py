from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2697",
    "page_type": "人物目录详情页",
    "structure_group": "hunan_tcm_leader_details_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "directory_detail",
    "collector": "static_http",
    "parser": "parse_page",
    "leader_region_selector": ".main_list_right table.table_list > tbody > tr",
    "name_selector": "td > a[title][href]",
    "duty_selector": "详情页 li.jdld_leader_zw 中标签为职务的节点",
    "detail_link_selector": "td > a[title][href]",
    "content_scope": {
        "start_anchor": "索引号",
        "end_anchor": "友情链接",
        "include_selectors": [".main_list_right table.table_list"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "person_name_link",
        "detail_collector_type": "requests",
        "detail_link_selector": ".main_list_right table.table_list td > a[title][href]",
        "detail_name_selector": "li.jdld_leader_tit",
        "detail_duty_selector": "li.jdld_leader_zw",
        "detail_content_selector": "div.jgld_leader",
        "max_detail_links": 20,
    },
    "risk_flag": "详情页职务与工作职责使用相同类名，必须按字段标签区分",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def _clean_name(value: str) -> str:
    """清理并校验中文姓名。"""
    name = re.sub(r"\s+", "", value)
    return name if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) else ""


def _fetch_detail(session: requests.Session, detail_url: str) -> requests.Response:
    """正常校验证书；仅在该站SSL握手异常时降级重试。"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        return session.get(detail_url, timeout=60, headers=headers)
    except requests.exceptions.SSLError:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return session.get(detail_url, timeout=60, headers=headers, verify=False)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录表格顺序抓取详情页姓名和职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for row in soup.select(".main_list_right table.table_list > tbody > tr"):
        link = row.select_one("td > a[title][href]")
        if link is None:
            continue
        name = _clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href", "")))
        if (
            not name
            or urlparse(detail_url).netloc != urlparse(final_url).netloc
            or not re.fullmatch(r"/tcm/xxgk/jgzn/jgld/\d{6}/t\d+_\d+\.html", urlparse(detail_url).path)
            or detail_url in seen_urls
        ):
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))
    if not candidates:
        raise RuntimeError("机构领导表格未解析出有效详情链接")

    rows: list[dict[str, str]] = []
    for expected_name, detail_url in candidates:
        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy="raw_http",
            timeout=60,
        )
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        actual_node = detail_soup.select_one("div.jgld_leader li.jdld_leader_tit")
        actual_name = _clean_name(actual_node.get_text(" ", strip=True) if actual_node else "")
        duty = ""
        for field in detail_soup.select("div.jgld_leader li.jdld_leader_zw"):
            text = _clean_text(field.get_text(" ", strip=True))
            match = re.fullmatch(r"职\s*务\s*[：:]\s*(.+)", text)
            if match:
                duty = _clean_text(match.group(1))
                break
        if actual_name != expected_name or not duty:
            raise RuntimeError(f"详情页姓名或职务字段无效：{expected_name}")
        rows.append(
            {
                "name": expected_name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": (
                    "strategy=css+requests；directory=.main_list_right table.table_list tbody tr；"
                    "detail=div.jgld_leader；name=li.jdld_leader_tit；"
                    "duty=li.jdld_leader_zw且标签为职务；exclude=工作职责字段"
                ),
            }
        )
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
