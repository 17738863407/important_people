from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2313',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'custom_nc_sfj_leader_cards_v2',
 'leader_region_selector': '.Jxsf_154',
 'name_selector': '.Jxsf_155:first-child, .Jxsf_160:first-child',
 'duty_selector': '.Jxsf_155:nth-child(2), .Jxsf_160:nth-child(2)',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'max_detail_links': 0},
 'risk_flag': '同页卡片后方包含大量履历；仅解析每张卡片前两个直属字段，并在职责标记前截断职务',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.Jxsf_154',
                     'name_selector': '.Jxsf_155:first-child, .Jxsf_160:first-child',
                     'duty_selector': '.Jxsf_155:nth-child(2), .Jxsf_160:nth-child(2)',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '当前领导之窗 HTML 直接包含姓名、简介及履历'},
             'migration': {'source': 'current_online_cards',
                           'verified_status': 'verified_online',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    normalized = " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())
    return re.sub(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])", "", normalized)


def extract_duty(text: str) -> str:
    """从当前人物卡片简介中提取现任职务，排除后续职责说明。"""
    match = re.search(r"现任(.+?)(?=，(?:主持|协助|负责|分管|联系)|。|$)", text)
    if match:
        return clean_text(match.group(1)).rstrip("。；; ")
    segments = [clean_text(part).rstrip("。；; ") for part in re.split(r"[，,]", text) if clean_text(part)]
    return segments[-1] if segments and re.search(r"巡视员|调研员", segments[-1]) else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()

    for card in soup.select(".Jxsf_154"):
        fields = [node for node in card.find_all("div", recursive=False) if "Jxsf_155" in (node.get("class") or []) or "Jxsf_160" in (node.get("class") or [])]
        if len(fields) < 2:
            continue
        name = re.sub(r"\s+", "", clean_text(fields[0].get_text(" ", strip=True)))
        text = clean_text(fields[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        duty = extract_duty(text)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "selector_summary": ".Jxsf_154 direct name/profile fields; duty before responsibility marker",
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
