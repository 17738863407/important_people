from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2955",
    "domain": "wlt.jiangsu.gov.cn",
    "page_type": "人物目录详情页",
    "structure_group": "jiangsu_wlt_leader_directory_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_to_detail",
    "collector": "playwright_hidden",
    "parser": "JIANGSU_WLT_LEADER_DIRECTORY_DETAIL_V1",
    "leader_region_selector": ".Rcont.zn_cont",
    "detail_link_selector": ".ldlb-txt li a[href]",
    "detail_person_selector": ".Rcont.zn_cont .ldxx span",
    "locator_strategy": "custom_parse_page",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "普通HTTP当前返回521，入口和详情页需要无头Playwright渲染",
    "confidence": "high",
}


def clean_inline(value: str) -> str:
    """清理HTML排版空白，不改变原始职务语义。"""
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_name(value: str) -> str:
    """清除姓名中的网页排版空白。"""
    return re.sub(r"\s+", "", value or "").strip()


def validate_detail_url(source_url: str, detail_url: str) -> None:
    """只接受当前站点领导栏目中的独立个人页面。"""
    source = urlparse(source_url)
    detail = urlparse(detail_url)
    if detail.scheme not in {"http", "https"} or detail.netloc != source.netloc:
        raise ValueError(f"人物详情链接不是入口同源页面：{detail_url}")
    if not re.fullmatch(r"/col/col\d+/index\.html", detail.path):
        raise ValueError(f"人物详情链接路径异常：{detail_url}")


def fetch_detail_html(detail_url: str, timeout_seconds: int) -> tuple[str, str]:
    """通过项目公共在线采集器读取人物详情页。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    result = fetch_html_with_strategy(
        detail_url,
        strategy="online",
        force_browser=True,
        timeout=timeout_seconds,
    )
    return result.html, result.final_url or detail_url


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按当前领导目录顺序逐页提取姓名、原始职务和真实详情链接。"""
    from crawler_core.settings import get_settings

    source_url = str(page_rule.get("url") or final_url).strip()
    current_url = str(final_url or source_url).strip()
    list_soup = BeautifulSoup(html, "html.parser")
    link_selector = str(page_rule["detail_link_selector"])
    person_selector = str(page_rule["detail_person_selector"])
    link_nodes = list_soup.select(link_selector)
    if not link_nodes:
        raise ValueError("当前入口未找到领导目录链接")

    timeout_seconds = get_settings().browser_timeout_seconds
    seen_urls: set[str] = set()
    rows: list[dict[str, str]] = []

    for node in link_nodes:
        expected_name = normalize_name(node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", expected_name):
            raise ValueError(f"领导目录姓名格式异常：{expected_name}")

        detail_url = urljoin(current_url or source_url, str(node.get("href", "")).strip())
        validate_detail_url(source_url, detail_url)
        if detail_url in seen_urls:
            raise ValueError(f"领导目录出现重复详情链接：{detail_url}")
        seen_urls.add(detail_url)

        if detail_url.rstrip("/") == current_url.rstrip("/"):
            detail_html = html
            detail_final_url = current_url
        else:
            detail_html, detail_final_url = fetch_detail_html(detail_url, timeout_seconds)
        validate_detail_url(source_url, detail_final_url)

        detail_soup = BeautifulSoup(detail_html, "html.parser")
        person_node = detail_soup.select_one(person_selector)
        if person_node is None:
            raise ValueError(f"详情页缺少姓名职务节点：{detail_final_url}")
        parts = [clean_inline(value) for value in person_node.stripped_strings if clean_inline(value)]
        if len(parts) < 2:
            raise ValueError(f"详情页姓名职务字段不完整：{detail_final_url}")

        actual_name = normalize_name(parts[0])
        if actual_name != expected_name:
            raise ValueError(
                f"详情页姓名与目录不一致：目录={expected_name}，详情={actual_name}，URL={detail_final_url}"
            )
        evidence = clean_inline(" ".join(parts[1:]))
        if not evidence:
            raise ValueError(f"详情页缺少原始职务：{actual_name}")

        output_detail_url = "" if detail_final_url.rstrip("/") == source_url.rstrip("/") else detail_final_url
        rows.append(
            {
                "name": actual_name,
                "evidence": evidence,
                "detail_url": output_detail_url,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
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
