from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0828",
    "page_type": "人物表格页",
    "structure_group": "haikou_compound_profile_current_sentence",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#ContentRegion",
    "name_selector": "人物块段首姓名及性别",
    "duty_selector": "当前人物块完整现任句或明确党委职务片段",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["#ContentRegion"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "单一正文合并多人，按姓名性别边界切分并禁止跨人物搜索现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_evidence(value: str) -> str:
    """删除固定现任标签和纯句末句号，保留人物块内完整任职语义。"""
    evidence = re.sub(r"^现任\s*", "", clean_text(value))
    return re.sub(r"。$", "", evidence).strip()


def split_profiles(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?P<name>[\u4e00-\u9fff]{2,4})\s*[，,]\s*(?:男|女)", text))
    profiles: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        profiles.append((match.group("name"), text[match.start() : end]))
    return profiles


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#ContentRegion")
    if region is None:
        raise ValueError("未找到领导信息正文 #ContentRegion")
    text = clean_text(region.get_text(" ", strip=True))
    rows: list[dict[str, str]] = []
    for name, profile in split_profiles(text):
        current_match = re.search(r"现任[^。]*(?:。|$)", profile)
        if current_match:
            evidence = clean_text(current_match.group(0))
        else:
            duty_match = re.search(r"((?:党委|党组)[^。]*(?:主任|书记|巡视员|调研员)[^。]*)。", profile)
            evidence = f"{clean_text(duty_match.group(1))}。" if duty_match else ""
        if not evidence:
            raise ValueError(f"当前人物简介块缺少可验证的现任职务：{name}")
        evidence = clean_evidence(evidence)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "selector_summary": "#ContentRegion姓名性别人物块内现任句或党委职务片段",
            }
        )
    if not rows:
        raise ValueError("领导信息正文未发现可验证的人物简介块")
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
