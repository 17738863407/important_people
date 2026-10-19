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
    "rule_id": "3948",
    "domain": "ny.hnzx.gov.cn",
    "page_type": "正文人物图片与姓名职务段落",
    "structure_group": "henan_cppcc_article_leader_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_nanyang_cppcc_article_v1",
    "leader_region_selector": "#Content",
    "name_selector": "#Content > p",
    "duty_selector": "#Content > p",
    "content_scope": {"include_selectors": ["#Content"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "元数据Description含历史名单，必须只解析当前正文Content直属人物段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "#Content", "record_selector": ":scope > p"},
        "text_boundary": "姓名之后的市政协为现职证据起点",
        "api": {"enabled": False, "reason": "当前正文已直接包含姓名和完整现职字段"},
    },
}


def normalize_text(value: str) -> str:
    """删除富文本编辑器产生的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅从当前正文直属段落拆分姓名和以“市政协”开头的现职证据。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#Content")
    if region is None:
        raise RuntimeError("未找到领导正文 #Content")
    rows: list[dict[str, str]] = []
    for paragraph in region.select(":scope > p"):
        text = normalize_text(paragraph.get_text(" ", strip=True))
        boundary = text.find("市政协")
        if boundary <= 0:
            continue
        name = text[:boundary]
        duty = text[boundary:]
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name):
            continue
        if not re.search(r"主席|秘书长|巡视员", duty):
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#Content直属段落；市政协文本边界拆分姓名与现职",
            }
        )
    if not rows:
        raise RuntimeError("当前领导正文未解析出有效人物段落")
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
