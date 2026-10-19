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
    """清除网页排版空白，不改写正文语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def valid_name(value: str) -> bool:
    """校验院领导列表中的中文姓名。"""
    return bool(re.fullmatch(r"[\u3400-\u9fff·]{2,10}", value))


def clean_duty_evidence(value: str) -> str:
    """整理现职句分隔符，完整保留审判委员会职务和法官等级。"""
    pieces = [clean_text(item).strip("，,。；; ") for item in re.split(r"[、，,；;]", value)]
    return "、".join(item for item in pieces if item)


def extract_current_duty(name: str, text: str) -> str:
    """从当前人物详情正文提取最新的现职或任免结果。"""
    paragraphs = [clean_text(item) for item in text.splitlines() if clean_text(item)]
    for paragraph in reversed(paragraphs):
        match = re.search(r"现任(?P<duty>[^。；;]+)", paragraph)
        if match:
            return clean_duty_evidence(match.group("duty"))

    joined = "。".join(paragraphs)
    patterns = (
        rf"{re.escape(name)}当选(?P<duty>[^。；;]*?人民法院院长)",
        rf"任命{re.escape(name)}为(?P<duty>[^。；;]+)",
        rf"{re.escape(name)}代理(?P<duty>[^。；;]*?院长)职务",
    )
    candidates: list[tuple[int, str]] = []
    for pattern in patterns:
        candidates.extend((match.start(), match.group("duty")) for match in re.finditer(pattern, joined))
    return clean_duty_evidence(max(candidates)[1]) if candidates else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按院领导列表原序抓取独立详情页并提取目标领导职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html or "", "html.parser")
    region = next(
        (
            section
            for section in soup.select(".content")
            if clean_text((section.select_one(".title h2") or section).get_text(" ", strip=True)).startswith("院领导")
        ),
        None,
    )
    if region is None:
        raise RuntimeError("入口页未找到标题为“院领导”的内容区域")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in region.select("ul li .left a[title][href]"):
        name = clean_text(str(link.get("title") or link.get_text(" ", strip=True))).replace(" ", "")
        if not valid_name(name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        detail = fetch_html_with_strategy(detail_url, strategy="raw_http", timeout=30, referer=final_url)
        detail_soup = BeautifulSoup(detail.html or "", "html.parser")
        title_node = detail_soup.select_one(".detail .b_title p")
        detail_name = clean_text(title_node.get_text(" ", strip=True) if title_node else "").replace(" ", "")
        if detail_name != name:
            raise RuntimeError(f"详情页姓名与列表不一致：列表={name}，详情={detail_name or '<空>'}")
        body = detail_soup.select_one(".detail .text")
        if body is None:
            raise RuntimeError(f"人物 {name} 的详情页缺少正文 .detail .text")
        body_text = "\n".join(clean_text(node.get_text(" ", strip=True)) for node in body.select("p"))
        evidence = extract_current_duty(name, body_text)
        if not evidence:
            raise RuntimeError(f"人物 {name} 的详情页未找到可验证目标领导职务")
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail.final_url,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "院领导列表原序；独立详情正文中的现任或最新任免句；完整保留委员职务与法官等级",
            }
        )
        seen.add(name)
    if not rows:
        raise RuntimeError("院领导列表未提取到有效人物")
    return rows


PAGE_RULE = {
    "rule_id": "4520",
    "domain": "ahfy.ahcourt.gov.cn",
    "page_type": "院领导列表转人物详情",
    "structure_group": "chinacourt_leader_list_detail_current_duty_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出并逐页请求详情",
    "extract_mode": "list_to_detail",
    "parser": "page_anhui_high_court_leader_detail_v1",
    "leader_region_selector": ".content中标题为院领导的区域",
    "name_selector": "ul li .left a[title][href]",
    "duty_selector": ".detail .text中的现任或最新任免句",
    "detail_link_selector": "ul li .left a[title][href]",
    "detail_strategy": {"required": True, "mode": "list_to_detail", "detail_collector_type": "raw_http"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "详情正文含履历、委员职务及法官等级；只取现任或最新任免结果，并完整保留现职句中的委员职务与法官等级",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        PAGE_RULE,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"尝试链路：{runtime_context.get('attempted_collectors', [])}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
