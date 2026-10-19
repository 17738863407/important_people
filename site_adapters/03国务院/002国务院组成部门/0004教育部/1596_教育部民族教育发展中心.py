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
    "rule_id": "1596",
    "page_type": "职务分组名单页",
    "structure_group": "中心领导职务分组段落",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "MoeNationalityColonGroupsParser_v2",
    "leader_region_selector": ".moe-main-section .list p",
    "name_selector": "冒号后名单",
    "duty_selector": "完整职务分组段落",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "普通HTTP受412限制，需浏览器取得正文；多人职务组必须为每人重复完整分组证据，页面无人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按中心领导分组段落及行内名单顺序抽取人物。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in soup.select(".moe-main-section .list p"):
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        matched = re.fullmatch(r"(.+?)[：:]\s*(.+)", evidence)
        if not matched:
            continue
        duty = matched.group(1).strip()
        for value in re.split(r"[、，,]", matched.group(2)):
            name = re.sub(r"\s+", "", value)
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names:
                continue
            seen_names.add(name)
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "parser": PAGE_RULE["parser"],
                    "selector_summary": ".moe-main-section .list p；职务：名单；按段落和行内顿号顺序；每人完整分组证据",
                }
            )
    if not records:
        raise RuntimeError("中心领导职务分组段落未解析到人物记录")
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
