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


def clean_name(value: str) -> str:
    """移除姓名节点中的排版空格。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " "))


def parse_page(
    html: str,
    final_url: str,
    _page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按领导列表顺序抓取详情，并解析简介开头的当前职务字段。"""
    from crawler_core.fetcher import fetch_many_by_chrome_debug

    soup = BeautifulSoup(html, "html.parser")
    leader_list = soup.select_one(".xxgk-mainContent > ul.pageList.newsList")
    if leader_list is None:
        raise ValueError("未找到领导信息列表 .xxgk-mainContent > ul.pageList.newsList")
    if not final_url:
        raise ValueError("在线采集结果缺少最终入口网址")

    links: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    for link in leader_list.select("li > a[href]"):
        title = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        name = clean_name(re.sub(r"同志主要简历$", "", title))
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if not href or href.lower().startswith(("javascript:", "mailto:", "#")):
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        links.append((name, urljoin(final_url, href)))

    if not links:
        raise ValueError("领导信息列表未发现有效人物详情链接")

    rows: list[dict[str, str]] = []
    selector_summary = (
        "strategy=custom_parse_page；leader=.xxgk-mainContent > ul.pageList.newsList；"
        "name=li > a[href]标题去除同志主要简历；"
        "duty=#zoomcon.article-content内现任短语或党员字段后的明确职务短句；detail=li > a[href]"
    )
    detail_results = fetch_many_by_chrome_debug(
        [detail_url for _name, detail_url in links],
        timeout=40,
        max_workers=2,
    )
    for (name, detail_url), detail_result in zip(links, detail_results, strict=True):

        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        profile = detail_soup.select_one("#zoomcon.article-content")
        if profile is None:
            raise ValueError(f"{name}详情页未找到 #zoomcon.article-content")
        profile_text = clean_text(profile.get_text(" ", strip=True))

        duty = ""
        evidence = ""
        current_match = re.search(r"现任[^；;。]*", profile_text)
        if current_match is not None:
            duty = re.sub(r"^现任\s*", "", current_match.group(0))
            evidence = duty
        else:
            first_sentence = profile_text.split("。", maxsplit=1)[0]
            status_match = re.search(
                r"(?:中共党员|群众|民盟盟员)[，,]\s*(?P<duty>[^。；;]+)$",
                first_sentence,
            )
            if status_match is not None:
                candidate_duty = clean_text(status_match.group("duty"))
                if re.search(r"(书记|局长|主任|调研员|党组成员|党委委员)", candidate_duty):
                    duty = candidate_duty
                    evidence = duty
        if not duty:
            raise ValueError(f"{name}详情简介未找到可靠当前职务字段")
        if name not in clean_name(profile_text):
            raise ValueError(f"{name}详情简介无法回指列表姓名")

        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": evidence,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": "page_inline_nanchang_water_profile_v1",
                "selector_summary": selector_summary,
            }
        )

    return rows


def run_directory_adapter(project_dir: Path) -> Path:
    """使用Chrome读取入口及详情，并统一导出十三列结果。"""
    from crawler_core.business_sources import apply_business_source, normalize_script_sequence
    from crawler_core.exporter import export_records
    from crawler_core.fetcher import fetch_by_chrome_debug
    from crawler_core.naming import build_output_name
    from crawler_core.runner import (
        apply_business_location,
        normalize_inline_rows,
        normalize_record_source_urls,
        prepare_records_for_export,
    )

    page_rule = apply_business_source(dict(PAGE_RULE))
    list_result = fetch_by_chrome_debug(str(page_rule["url"]), timeout=40)
    raw_rows = parse_page(list_result.html, list_result.final_url, page_rule)
    rows = normalize_inline_rows(page_rule, raw_rows)
    normalize_record_source_urls(page_rule, rows)
    apply_business_location(page_rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        row.script_sequence = normalize_script_sequence(page_rule["rule_id"])
    output_path = project_dir / "outputs" / build_output_name(page_rule["rule_id"], page_rule["organization"])
    export_records(output_path, rows)
    return output_path


PAGE_RULE = {
    "rule_id": "2847",
    "page_type": "人物目录详情页",
    "structure_group": "nanchang_water_profile_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_nanchang_water_profile_v1",
    "leader_region_selector": ".xxgk-mainContent > ul.pageList.newsList",
    "name_selector": "li > a[href]",
    "duty_selector": "#zoomcon.article-content[现任短语或党员字段后明确职务短句]",
    "detail_link_selector": "li > a[href]",
    "detail_strategy": {"required": False, "mode": "inline_detail_fetch"},
    "risk_flag": "系统DNS不能解析站点子域名，使用Chrome CDP并对详情页执行2路受控并发；详情简介只读取现任短语或党员字段后的明确职务短句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".xxgk-mainContent > ul.pageList.newsList",
            "name_selector": "li > a[href]",
            "duty_selector": "#zoomcon.article-content[现任短语或党员字段后明确职务短句]",
            "detail_link_selector": "li > a[href]",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态列表及详情页稳定提供姓名、独立人物链接和简介职务字段",
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

    output_path = run_directory_adapter(project_dir)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
