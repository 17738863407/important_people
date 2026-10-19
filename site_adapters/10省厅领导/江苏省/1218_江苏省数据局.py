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
    "rule_id": "1218",
    "domain": "jszwb.jiangsu.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jiangsu_data_direct_profile_blocks_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "combined_profiles",
    "collector": "static_http",
    "parser": "page_inline_jiangsu_data_direct_profile_blocks_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "全页div高度嵌套；必须限定.inner直接人物块及其标题div；图片原图链接不得作为人物详情",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_duty(value: str) -> str:
    """只清理标题字段中的排版空格。"""
    duty = clean_text(value)
    duty = re.sub(r"\s*([、，,；;])\s*", r"\1", duty)
    return duty.strip("，,；;。 ")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按.inner直接人物块顺序读取标题中的姓名与职务。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".inner")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for block in scope.find_all("div", recursive=False) if scope else []:
        direct_children = block.find_all("div", recursive=False)
        content = direct_children[1] if len(direct_children) >= 2 else None
        title = content.find("div", recursive=False) if content else None
        text = clean_text(title.get_text(" ", strip=True) if title else "")
        match = re.fullmatch(r"([\u3400-\u9fff·]{2,5})\s*[：:]\s*(.+)", text)
        if match is None:
            continue
        name = match.group(1)
        duty = clean_duty(match.group(2))
        if not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；row=.inner direct-div；"
                    "field=second-direct-div first-direct-div name-colon-duty；"
                    "exclude=profile-p+image-links"
                ),
            }
        )

    return records


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
