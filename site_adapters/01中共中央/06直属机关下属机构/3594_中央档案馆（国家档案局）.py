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


def normalize_space(text: str) -> str:
    """清理人物目录和详情简介中的排版空白，不改变网页原始语义。"""
    value = str(text or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def normalize_name(text: str) -> str:
    """删除姓名节点内仅由网页排版引入的空白。"""
    return re.sub(r"\s+", "", normalize_space(text))


def is_name(text: str) -> bool:
    """校验领导目录姓名节点中的常见中文姓名形式。"""
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", text))


def build_page_rule(rule_id: str) -> dict:
    """构造馆局领导目录及详情页经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "www.saac.gov.cn",
        "page_type": "人物目录详情页",
        "structure_group": "saac_leader_directory_detail_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "list_to_detail",
        "collector": "static_http",
        "parser": "page_saac_leader_directory_detail_v1",
        "leader_region_selector": ".w1060.bgfff",
        "name_selector": ".center > dl.leader_name dd p a[title][href]",
        "duty_selector": ".wzcon ucapcontent",
        "detail_link_selector": ".center > dl.leader_name dd p a[title][href]",
        "content_scope": {
            "include_selectors": [".w1060.bgfff"],
            "exclude_selectors": ["script", "style"],
        },
        "detail_strategy": {
            "required": True,
            "mode": "list_to_detail",
            "detail_collector_type": "raw_http",
            "detail_link_selector": ".center > dl.leader_name dd p a[title][href]",
            "candidate_links": [],
        },
        "risk_flag": "列表页职务仅存在于HTML注释，必须从当前人物详情页可见简介提取",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".w1060.bgfff",
                "item_selector": ".center > dl.leader_name",
                "name_selector": "dd p a[title][href]",
                "detail_link_selector": "dd p a[title][href]",
                "detail_content_selector": ".wzcon ucapcontent",
            },
            "api": {"enabled": False, "reason": "静态HTML目录和人物详情简介可稳定回指姓名与现职"},
        },
    }


def extract_detail_row(detail_html: str, detail_url: str, expected_name: str, parser: str) -> dict[str, str]:
    """从当前人物详情页简介首句中提取姓名及性别字段前的完整现职。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    title_link = soup.select_one("ucaptitle a[title]")
    content = soup.select_one(".wzcon ucapcontent")
    detail_name = normalize_name(title_link.get_text(" ", strip=True) if title_link else "")
    biography = normalize_space(content.get_text(" ", strip=True) if content else "")
    if detail_name != expected_name:
        raise RuntimeError(f"详情页姓名与目录不一致：目录={expected_name}，详情={detail_name or '<空>'}")

    duty_match = re.match(
        rf"^{re.escape(expected_name)}[，,](?P<duty>.+?)[，,](?:男|女)[，,]",
        biography,
    )
    if duty_match is None:
        raise RuntimeError(f"详情页简介缺少可验证的姓名—现职—性别字段边界：{detail_url}")
    duty = normalize_space(duty_match.group("duty")).strip("，,。.;； ")
    if not duty:
        raise RuntimeError(f"详情页简介未解析出完整现职：{detail_url}")

    return {
        "name": expected_name,
        "duty": duty,
        "evidence": duty,
        "detail_url": detail_url,
        "parser": parser,
        "selector_summary": (
            "strategy=custom_parse_page；list=.w1060.bgfff>.center>dl.leader_name；"
            "detail=.wzcon ucapcontent；fields=姓名后至性别字段前现职"
        ),
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导目录原始顺序发现详情链接，并逐页提取完整馆局现职。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".w1060.bgfff")
    if region is None:
        raise RuntimeError("入口页未找到馆局领导内容区域 .w1060.bgfff")

    candidates: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for card in region.select(":scope > .center > dl.leader_name"):
        link = card.select_one("dd p a[title][href]")
        if link is None:
            continue
        name = normalize_name(link.get_text(" ", strip=True))
        href = str(link.get("href", "")).strip()
        detail_url = urljoin(final_url or str(page_rule.get("url", "")), href)
        if not is_name(name) or not href or name in seen_names or detail_url in seen_urls:
            continue
        seen_names.add(name)
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))
    if not candidates:
        raise RuntimeError("馆局领导目录未解析出可验证姓名和详情链接")

    rows: list[dict[str, str]] = []
    parser = str(page_rule.get("parser", ""))
    for name, detail_url in candidates:
        detail_result = fetch_html_with_strategy(detail_url, strategy="raw_http")
        rows.append(extract_detail_row(detail_result.html, detail_result.final_url, name, parser))
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(page_rule, globals(), runtime_context=runtime_context)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"尝试链路：{runtime_context.get('attempted_collectors', [])}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3594"
    main(rule_id_value)
