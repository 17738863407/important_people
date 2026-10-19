from __future__ import annotations

import re
import ssl
import sys
from pathlib import Path
from urllib import request as urllib_request

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1916", "page_type": "人物目录详情页", "structure_group": "www_ningbo_gov_cn_live_api_leader_detail_duty_guard_v2", "reuse_scope": "single_page", "load_mode": "接口数据加载", "fetch_mode": "online", "extract_mode": "custom_parse_page", "collector": "online_http", "parser": "page_ningbo_science_live_api_detail_duty_guard_v2",
    "leader_region_selector": "page/build/unit分页接口人物列表", "name_selector": "接口人物链接文本及详情姓名字段", "duty_selector": "详情页职务字段；职责误填时使用同页完整现任句", "detail_link_selector": "接口返回的同栏目/art/人物链接", "detail_strategy": {"required": True, "mode": "live_api_to_detail", "max_detail_links": 80}, "risk_flag": "个别详情页将分工误填入职务标签；职责字段不得作为职务，必须回退同页简历完整现任句", "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "page/build/unit分页接口人物列表", "name_selector": "详情姓名字段", "duty_selector": "职务字段或同页简历现任句", "detail_link_selector": "同栏目/art/人物链接"}, "api": {"enabled": True, "reason": "入口页script声明稳定page/build/unit分页接口"}},
}


def open_ningbo_url(request: object, timeout: int = 25):
    """仅为当前宁波官网自签名证书链提供站点级降级。"""
    return urllib_request.urlopen(
        request,
        timeout=timeout,
        context=ssl._create_unverified_context(),
    )


def compact_layout(text: str) -> str:
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    from crawler_core import www_ningbo_gov_cn_leader_info as ningbo_leader
    from crawler_core.www_ningbo_gov_cn_leader_info import _collect_live_api_links, _fetch_html, _parse_detail_page

    ningbo_leader.urlopen = open_ningbo_url

    links = _collect_live_api_links(page_rule)
    if not links:
        raise RuntimeError("宁波领导信息分页接口未返回人物链接")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for list_name, detail_url in links:
        try:
            detail_html = _fetch_html(detail_url)
            detail_name, duty, _ = _parse_detail_page(detail_html, list_name)
        except Exception as exc:
            raise RuntimeError(f"人物{list_name}详情页采集或解析失败：{exc}") from exc
        name = detail_name or list_name
        if not name or not duty:
            raise RuntimeError(f"人物{list_name}详情页缺少姓名或职务依据")
        if re.match(r"^(?:协助|负责|分管|联系|主持)(?:局|处|工作|党组|党委)", duty):
            detail_text = compact_layout(BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True))
            current_match = re.search(r"现任[^。]*。", detail_text)
            if current_match is None:
                raise RuntimeError(f"人物{name}职务标签为职责且详情页没有完整现任句")
            evidence = current_match.group(0)
        else:
            evidence = f"职务：{duty}"
        evidence = re.sub(r"^职务：\s*", "", evidence)
        evidence = re.sub(r"^现任\s*", "", evidence)
        evidence = re.sub(r"[（(]兼[）)]", "", evidence)
        evidence = re.sub(r"。\s*$", "", evidence)
        evidence = re.sub(r"\s*([、，])\s*", r"\1", evidence)
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": detail_url, "parser": str(page_rule.get("parser", "")), "selector_summary": "入口接口顺序；详情职务字段，职责误填时回退同页简历完整现任句"})
    if not rows:
        raise RuntimeError("宁波领导详情未提取到有效人物记录")
    return rows


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
