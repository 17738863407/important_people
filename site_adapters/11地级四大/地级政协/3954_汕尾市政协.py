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
    "rule_id": "3954",
    "domain": "www.swzx.gov.cn",
    "page_type": "领导简介正文",
    "structure_group": "shanwei_cppcc_biography_article",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_shanwei_cppcc_biography_v1",
    "leader_region_selector": "ucapcontent",
    "name_selector": "ucapcontent p",
    "duty_selector": "ucapcontent p",
    "content_scope": {"include_selectors": ["ucapcontent"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物段落混有性别、民族、出生年月和学历，必须在当前人物段内只截取汕尾市现职片段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "ucapcontent", "record_selector": "p"},
        "field_boundary": "段首姓名；汕尾市开头并以主席、秘书长或巡视员结尾的现职片段",
        "api": {"enabled": False, "reason": "静态正文当前人物段已直接包含姓名、简历字段和现职"},
    },
}


def compact_text(value: str) -> str:
    """删除富文本排版空白，不改变语义标点。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在每个当前人物简介段内提取段首姓名及明确的汕尾市现职片段。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("ucapcontent")
    if region is None:
        raise RuntimeError("未找到领导简介正文 ucapcontent")
    rows: list[dict[str, str]] = []
    for paragraph in region.select("p"):
        text = compact_text(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^([\u3400-\u9fff·]{2,4})[，,]", text)
        if not name_match:
            continue
        duties = re.findall(r"汕尾市[^，,。]*?(?:主席|秘书长|巡视员)", text)
        duties = list(dict.fromkeys(duties))
        if not duties:
            continue
        duty = "；".join(duties)
        rows.append(
            {
                "name": name_match.group(1),
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "ucapcontent当前人物段；段首姓名与汕尾市现职片段",
            }
        )
    if not rows:
        raise RuntimeError("领导简介正文未解析出有效人物现职")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
