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
    "rule_id": "3974", "domain": "www.fuzhou.gov.cn", "page_type": "机构职责页领导简介",
    "structure_group": "fuzhou_department_profile_numbered_leaders", "reuse_scope": "fuzhou_government_profile_platform",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_fuzhou_profile_numbered_leaders_v1", "leader_region_selector": "#detailCont .Custom_UnionStyle",
    "name_selector": "p", "duty_selector": "p",
    "content_scope": {"include_selectors": ["#detailCont .Custom_UnionStyle"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职责、简历、分工和机构设置混排，须仅匹配领导简介中的序号姓名括号职务段",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#detailCont .Custom_UnionStyle", "record_selector": "p"}, "text_pattern": "序号.姓名（职务）"},
}


def normalize_text(value: str) -> str:
    """删除富文本字段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅解析“领导简介”中序号、姓名、括号职务结构。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#detailCont .Custom_UnionStyle")
    if region is None:
        raise RuntimeError("未找到机构详情正文")
    rows: list[dict[str, str]] = []
    in_leaders = False
    pattern = re.compile(r"^\d+[.．、]([\u3400-\u9fff·]{2,4})[（(](.+)[）)]$")
    for paragraph in region.select("p"):
        text = normalize_text(paragraph.get_text(" ", strip=True))
        if "领导简介" in text:
            in_leaders = True
            continue
        if in_leaders and re.match(r"^[四五六七八九十]+、", text):
            break
        match = pattern.fullmatch(text) if in_leaders else None
        if not match:
            continue
        name, duty = match.groups()
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "领导简介区序号姓名括号职务段"})
    if not rows:
        raise RuntimeError("领导简介未解析出有效人物")
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
