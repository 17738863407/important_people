from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4565",
    "page_type": "检察院领导简介段落",
    "structure_group": "shanghai_procuratorate_biography_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "浏览器渲染（普通HTTP客户端返回403）",
    "force_browser": True,
    "extract_mode": "biography_paragraphs",
    "parser": "page_shanghai_procuratorate_biography_paragraphs_v1",
    "leader_region_selector": "td 内含现任句的p",
    "name_selector": "p strong",
    "duty_selector": "p文本中的现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "富文本由人物照片与简介段落交替组成；只解析同时含strong姓名和“现任”句的段落，并保留其中全部委员职务。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按页面原序读取人物简介中的姓名与现任职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict[str, str]] = []
    for paragraph in soup.select("p"):
        text = re.sub(r"[\s\u00a0\u3000]+", "", paragraph.get_text(" ", strip=True))
        names = [re.sub(r"[\s\u00a0\u3000]+", "", node.get_text(" ", strip=True)) for node in paragraph.find_all("strong")]
        name = next((candidate for candidate in names if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", candidate)), "")
        if not name or "现任" not in text:
            continue
        match = re.search(r"现任([^。]+)", text)
        evidence = match.group(1) if match else ""
        parts = [part for part in re.split(r"[，,、；;]", evidence) if part]
        evidence = "、".join(parts)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            continue
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": "富文本p按strong姓名与现任句原序提取；保留全部委员职务"})
    if not rows:
        raise RuntimeError("领导介绍未提取到领导人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
