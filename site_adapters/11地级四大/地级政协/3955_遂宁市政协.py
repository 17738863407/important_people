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
    "rule_id": "3955",
    "domain": "www.snzx.gov.cn",
    "page_type": "人物图片与职务姓名段落",
    "structure_group": "suining_cppcc_photo_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_suining_cppcc_paragraphs_v1",
    "leader_region_selector": ".content > div[class^='wen_neirong']",
    "name_selector": "p",
    "duty_selector": "p",
    "content_scope": {"include_selectors": [".content > div[class^='wen_neirong']"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "图片和空段落较多，且职务、姓名可能分属相邻span，须以遂宁市政协前缀和尾部姓名边界解析",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".content > div[class^='wen_neirong']", "record_selector": "p"},
        "text_pattern": "^遂宁市政协现职 + 空白 + 中文姓名$",
        "api": {"enabled": False, "reason": "静态正文已直接包含领导职务姓名文本"},
    },
}


def normalize_spaces(value: str) -> str:
    """将富文本的各类排版空白压缩为单个半角空格。"""
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从图片间的职务姓名段落按尾部空白边界提取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".content > div[class^='wen_neirong']")
    if region is None:
        raise RuntimeError("未找到政协领导正文容器")
    rows: list[dict[str, str]] = []
    pattern = re.compile(r"^(遂宁市政协.+?)\s+([\u3400-\u9fff·]{2,4})$")
    for paragraph in region.select("p"):
        text = normalize_spaces(" ".join(paragraph.stripped_strings))
        match = pattern.fullmatch(text)
        if not match:
            continue
        duty, name = match.groups()
        if not re.search(r"主席|秘书长", duty):
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "正文图片间以遂宁市政协开头的职务姓名段落",
            }
        )
    if not rows:
        raise RuntimeError("政协领导正文未解析出有效职务姓名段落")
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
