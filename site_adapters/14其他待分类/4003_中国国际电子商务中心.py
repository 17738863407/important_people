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


PAGE_RULE = {
    "rule_id": "4003",
    "page_type": "中心领导姓名职务连续文本页",
    "structure_group": "ciecc_leader_text_sequence",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_ciecc_leader_text_sequence_v1",
    "leader_region_selector": "中心领导正文",
    "name_selector": "职务文本紧邻前置短姓名",
    "duty_selector": "中国国际电子商务中心/有限公司职务行",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "中心领导",
        "end_anchor": "网站页脚",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文无详情链接；以机构全称开头的职务行必须仅归属其紧邻前置姓名。",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验实时HTML正文按姓名后紧随一至两条本中心或所属公司职务排列。",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "text": {
            "name_rule": "2至4个汉字且下一文本为目标机构职务",
            "duty_prefixes": ["中国国际电子商务中心", "中国国际电子商务有限公司"],
        },
        "api": {"enabled": False, "reason": "静态HTML正文已完整提供姓名和职务"},
        "migration": {"verified_status": "verified"},
    },
}


def clean_text(value: str) -> str:
    """清理页面排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def is_duty_text(value: str) -> bool:
    """判断文本是否为当前页面明确标注的任职机构职务行。"""
    return value.startswith(("中国国际电子商务中心", "中国国际电子商务有限公司"))


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按正文原顺序抽取“姓名—紧随职务行”结构。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    texts = [clean_text(text) for text in soup.stripped_strings]
    rows: list[dict[str, str]] = []
    index = 0
    while index < len(texts) - 1:
        name = texts[index]
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not is_duty_text(texts[index + 1]):
            index += 1
            continue
        duties: list[str] = []
        duty_index = index + 1
        while duty_index < len(texts) and is_duty_text(texts[duty_index]):
            duties.append(texts[duty_index].rstrip("。"))
            duty_index += 1
        duty = "；".join(dict.fromkeys(duties))
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "中心领导正文中姓名及紧随机构职务行",
            }
        )
        index = duty_index
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
