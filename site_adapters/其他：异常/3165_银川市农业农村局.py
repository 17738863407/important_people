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


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def clean_name(value: str) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " "))


def parse_page(
    html: str,
    _final_url: str,
    _page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """核验工作分工通知是否同时公开姓名和可用职务依据。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".xxgk-xl-text .view")
    if region is None:
        raise ValueError("未找到领导工作分工正文 .xxgk-xl-text .view")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.xxgk-xl-text .view；"
        "row=直接子p且段首strong姓名后紧接同志；name=段首第一个strong；"
        "duty/evidence=页面仅有工作分工故留空；detail=none"
    )
    for paragraph in region.find_all("p", recursive=False):
        strong = paragraph.find("strong")
        if strong is None:
            continue
        name = clean_name(strong.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
        if re.match(rf"^{re.escape(name)}\s*同志", paragraph_text) is None:
            continue
        if name in seen_names:
            raise ValueError(f"领导工作分工正文出现重复段首姓名：{name}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": "",
                "detail_url": "",
                "confidence": "medium",
                "parser": "page_inline_yinchuan_agriculture_name_only_v1",
                "selector_summary": selector_summary,
            }
        )

    if rows:
        return rows
    raise ValueError("领导工作分工正文未解析出有效段首姓名")


PAGE_RULE = {
    "rule_id": "3165",
    "page_type": "领导工作分工页",
    "structure_group": "yinchuan_agriculture_name_assignment",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "article_name_only",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_agriculture_name_only_v1",
    "leader_region_selector": ".xxgk-xl-text .view",
    "name_selector": ".xxgk-xl-text .view > p > strong:first-of-type[段首后接同志]",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面只公开主持、负责、分管、联系和协助事项，没有现任职务字段；保留可验证姓名，职务依据按规则留空",
    "confidence": "medium",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".xxgk-xl-text .view",
            "name_selector": ".xxgk-xl-text .view > p > strong:first-of-type[段首后接同志]",
            "duty_selector": "",
            "detail_link_selector": "",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态工作分工通知以段首强标签稳定提供姓名，但没有可验证职务字段",
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
