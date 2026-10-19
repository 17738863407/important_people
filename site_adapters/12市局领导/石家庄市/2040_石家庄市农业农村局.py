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
    "rule_id": "2040", "page_type": "现任领导信息页", "structure_group": "sjz_agriculture_org_marker_lines_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_agriculture_org_marker_lines_v2",
    "leader_region_selector": "#conN > div", "name_selector": "机构职务起始锚点前姓名",
    "duty_selector": "石家庄市农业农村局或石家庄市纪委监委锚点起始原文", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名与职务可能无空格；空aiAssistRoot须排除",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物行顺序使用机构职务锚点拆分姓名与完整原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    records: list[object] = []
    seen_names: set[str] = set()
    for line in regions[0].find_all("div", recursive=False):
        text = clean_text(line.get_text(" ", strip=True))
        if not text:
            continue
        marker = re.search(r"石家庄市(?:农业农村局|纪委监委)", text)
        if marker is None or marker.start() <= 0:
            raise RuntimeError(f"人物行缺少机构职务起始锚点：{text}")
        name = re.sub(r"\s+", "", text[:marker.start()])
        evidence = clean_text(text[marker.start():])
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or name in seen_names:
            raise RuntimeError(f"人物姓名、职务异常或姓名重复：{name}")
        if line.select_one("a[href]") is not None:
            raise RuntimeError(f"人物行出现未审计链接：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("领导正文没有有效人物行")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
