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
    "rule_id": "0011",
    "page_type": "职务分组名单页",
    "structure_group": "yunnan_stats_parenthesized_roles_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "yunnan_stats_parenthesized_roles_v1",
    "leader_region_selector": ".acticle-content",
    "name_selector": "直属p开头至左括号",
    "duty_selector": "姓名后全角括号内文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "全角括号后内容为分管职责，只能提取括号内职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩正文中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序提取姓名及括号内职务，排除冒号后的分管职责。"""
    del final_url
    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")

    pattern = re.compile(
        r"^(?P<name>[\u3400-\u9fff·]{2,10})（(?P<evidence>[^（）]+)）[：:].+$"
    )
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in regions[0].select(":scope > p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        match = pattern.fullmatch(text)
        if match is None:
            continue
        name = match.group("name")
        evidence = clean_text(match.group("evidence")).rstrip("。")
        if not evidence:
            raise RuntimeError(f"人物职务为空：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": ".acticle-content直属p；姓名后全角括号内为职务，冒号后职责排除",
            }
        )

    if not rows:
        raise RuntimeError("领导正文没有可验证的‘姓名（职务）：职责’段落")
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
