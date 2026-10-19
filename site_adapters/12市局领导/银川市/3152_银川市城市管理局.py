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
    """解析合并页中“姓名，职务：分工”段落的标题部分。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".xxgk-xl-text .view")
    if region is None:
        raise ValueError("未找到领导班子正文 .xxgk-xl-text .view")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.xxgk-xl-text .view；"
        "row=span[data-index=6]:has(>strong)；name=>strong；"
        "duty=同段姓名后逗号至首个冒号；detail=none"
    )
    for span in region.select('span[data-index="6"]'):
        strong = span.find("strong", recursive=False)
        if strong is None:
            continue
        name = clean_name(strong.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        span_text = clean_text(span.get_text(" ", strip=True))
        heading_match = re.match(
            rf"^{re.escape(name)}\s*[,，]\s*([^:：]+)\s*[:：]",
            clean_name(span_text),
        )
        if heading_match is None:
            continue
        duty = clean_text(heading_match.group(1))
        heading = clean_text(re.split(r"[:：]", span_text, maxsplit=1)[0])
        if not duty:
            continue
        if name in seen_names:
            raise ValueError(f"领导班子正文出现重复姓名：{name}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_yinchuan_urban_heading_v1",
                "selector_summary": selector_summary,
            }
        )

    if not rows:
        raise ValueError("领导班子正文未解析出有效姓名与职务标题")
    return rows


PAGE_RULE = {
    "rule_id": "3152",
    "page_type": "多人物详情合并页",
    "structure_group": "yinchuan_urban_name_duty_assignment",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "article_heading_blocks",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_urban_heading_v1",
    "leader_region_selector": ".xxgk-xl-text .view",
    "name_selector": "span[data-index='6'] > strong",
    "duty_selector": "span[data-index='6'][文本结构=姓名，职务：分工]冒号前标题",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物段同节点混合职务和分工；只截取姓名后逗号至首个冒号的职务标题，排除全部分工及AB岗说明",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".xxgk-xl-text .view",
            "name_selector": "span[data-index='6'] > strong",
            "duty_selector": "span[data-index='6'][文本结构=姓名，职务：分工]冒号前标题",
            "detail_link_selector": "",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态正文以强结构姓名标签和冒号边界直接提供职务与分工",
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
