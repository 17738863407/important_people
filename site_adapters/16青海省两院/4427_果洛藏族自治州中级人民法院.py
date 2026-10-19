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


def normalize_profile_text(text: str) -> str:
    """清除简介段落中的排版空白，保留原有文字和标点。"""
    value = str(text or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """只在单人简介首段内提取明确写出的姓名和现任职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".detail > .text")
    if region is None:
        raise RuntimeError("页面未找到院长简介区域 .detail > .text")

    candidates = [
        normalize_profile_text(paragraph.get_text(" ", strip=True))
        for paragraph in region.select("p")
        if "现任" in paragraph.get_text(" ", strip=True)
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"院长简介中的现职段落数量异常：{len(candidates)}")

    match = re.fullmatch(
        r"(?P<name>[\u4e00-\u9fff·]{2,8})[，,].*?现任(?P<duty>[^。；;]+)[。.]?",
        candidates[0],
    )
    if match is None:
        raise RuntimeError("院长简介首段缺少可验证的“姓名—现任职务”句界")
    name = match.group("name")
    duty = match.group("duty").strip()
    if not duty:
        raise RuntimeError("院长简介现任职务为空")

    return [
        {
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": "",
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": (
                "strategy=custom_parse_page；region=.detail>.text；"
                "fields=含现任的单人简介首段；detail=none"
            ),
        }
    ]


PAGE_RULE = {
    "rule_id": "4427",
    "domain": "glzy.qhwsfy.gov.cn",
    "page_type": "单人领导简介页",
    "structure_group": "qinghai_court_single_profile_current_duty",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "profile_direct",
    "collector": "raw_http",
    "parser": "page_qinghai_court_single_profile_current_duty_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".detail > .text",
    "name_selector": "p",
    "duty_selector": "p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "正文包含完整履历，只能在当前人物简介首段的现任句中取证",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator": {
        "css": {
            "leader_region_selector": ".detail > .text",
            "profile_paragraph_selector": "p",
        },
        "api": {"enabled": False, "reason": "当前单人简介和现职由静态正文直接提供"},
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
