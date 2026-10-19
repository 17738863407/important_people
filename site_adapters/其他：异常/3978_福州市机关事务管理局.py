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
    "rule_id": "3978", "domain": "www.fuzhou.gov.cn", "page_type": "领导姓名与职责段落",
    "structure_group": "fuzhou_department_name_responsibility_leaders", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_fuzhou_name_responsibility_v1", "leader_region_selector": "#detailCont",
    "name_selector": "p", "duty_selector": "",
    "content_scope": {"include_selectors": ["#detailCont"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面仅有姓名及负责分管事项，无明确职务字段；不得将职责推断为职务",
    "confidence": "medium", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#detailCont", "record_selector": "p"}, "text_pattern": "领导简介章节内姓名：职责"},
}


def normalize_text(value: str) -> str:
    """合并Word富文本片段并删除排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """只提取领导简介中的明确姓名，不把后续职责文字当作现职。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#detailCont")
    if region is None:
        raise RuntimeError("未找到机构职责正文区域")
    rows: list[dict[str, str]] = []
    in_leaders = False
    for paragraph in region.select("p"):
        text = normalize_text(paragraph.get_text(" ", strip=True))
        if "领导简介" in text:
            in_leaders = True
            continue
        if in_leaders and re.match(r"^四、机构设置", text):
            break
        match = re.match(r"^([\u3400-\u9fff·]{2,4})[：:]", text) if in_leaders else None
        if not match:
            continue
        name = match.group(1)
        rows.append({"name": name, "duty": "", "evidence": "", "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "领导简介章节姓名冒号职责段；职责不转存为职务"})
    if not rows:
        raise RuntimeError("领导简介未解析出明确姓名")
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
