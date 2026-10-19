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
    "rule_id": "3527",
    "page_type": "人物列表完整页",
    "structure_group": "中国电信集团领导正文段落",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "ChinaTelecomLeaderParagraphParser_v2",
    "leader_region_selector": ".col-xs-12.col-sm-9.col-md-9",
    "name_selector": ".TRS_Editor p",
    "duty_selector": ".TRS_Editor p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "HTTP请求受412防护及动态CT6参数影响；公共在线链需浏览器取得正文DOM",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按集团领导正文中“姓名—职务—简介”的段落顺序抽取。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".col-xs-12.col-sm-9.col-md-9")
    if scope is None:
        raise RuntimeError("中国电信集团领导正文区域不存在")
    texts = [_clean_text(node.get_text(" ", strip=True)) for node in scope.select(".TRS_Editor p")]
    texts = [text for text in texts if text]
    records: list[dict] = []
    seen_names: set[str] = set()
    for index, name in enumerate(texts[:-1]):
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue
        evidence = texts[index + 1]
        if "中国电信集团有限公司" not in evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "集团领导TRS正文；姓名段落的下一非空段落为职务",
            }
        )
    if not records:
        raise RuntimeError("中国电信集团领导正文未解析到人物记录")
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
