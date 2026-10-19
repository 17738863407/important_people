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
    "rule_id": "3951",
    "domain": "www.jxpxzx.gov.cn",
    "page_type": "职务标题多人名单",
    "structure_group": "wordpress_cppcc_grouped_names",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_pingxiang_cppcc_names_v1",
    "leader_region_selector": "article.post .entry",
    "name_selector": ".entry > p",
    "duty_selector": ".entry > p",
    "content_scope": {"include_selectors": ["article.post .entry"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "副主席多人同处一段且性别标记夹入姓名，须按排版空白切分并只保留职务标题",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "article.post .entry", "record_selector": ":scope > p"},
        "group_labels": "市政协主席、市政协副主席、市政协秘书长",
        "api": {"enabled": False, "reason": "WordPress静态正文已直接包含分组标题和人物名单"},
    },
}


def compact_text(value: str) -> str:
    """删除标题中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_names(value: str) -> list[str]:
    """按正文排版空白切分多人名单，并删除紧随姓名的性别标记。"""
    cleaned = re.sub(r"[（(]女[）)]", "", value or "")
    return [item for item in re.split(r"[\s\u00a0\u3000]+", cleaned.strip()) if re.fullmatch(r"[\u3400-\u9fff·]{2,4}", item)]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文职务标题把紧随其后的姓名段落展开为人物记录。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("article.post .entry")
    if region is None:
        raise RuntimeError("未找到政协领导正文 article.post .entry")
    duty_by_label = {"市政协主席：": "市政协主席", "市政协副主席：": "市政协副主席", "市政协秘书长：": "市政协秘书长"}
    rows: list[dict[str, str]] = []
    current_duty = ""
    for paragraph in region.select(":scope > p"):
        raw_text = paragraph.get_text(" ", strip=True)
        label = compact_text(raw_text)
        if label in duty_by_label:
            current_duty = duty_by_label[label]
            continue
        if not current_duty:
            continue
        names = parse_names(raw_text)
        if not names:
            continue
        for name in names:
            rows.append(
                {
                    "name": name,
                    "duty": current_duty,
                    "evidence": current_duty,
                    "detail_url": "",
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": "article.post .entry直属段落；职务标题关联下一人物名单段",
                }
            )
        current_duty = ""
    if not rows:
        raise RuntimeError("政协领导正文未解析出有效人物名单")
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
