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
    "rule_id": "0060",
    "page_type": "人物列表完整页",
    "structure_group": "全国总工会全总领导列表",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "AcftuLeaderListParser_v2",
    "leader_region_selector": "ul.qzld li",
    "name_selector": "a",
    "duty_selector": "li中移除姓名后的职务文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "普通HTTP返回412，需由online浏览器链路取得当前领导列表DOM",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def _clean_evidence(value: str) -> str:
    """删除独立任职状态标记，保留具体职务与兼任机构。"""
    cleaned = re.sub(
        r"(?:<|＜|\(|（)\s*(?:挂职|兼|主持日常工作)\s*(?:>|＞|\)|）)",
        "",
        _clean_text(value),
    )
    return re.sub(r"\s*([、，；])\s*", r"\1", cleaned).strip("：: ")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析全总领导列表；无权威列表DOM时显式失败。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for item in soup.select("ul.qzld li"):
        name_node = item.select_one("a")
        if name_node is None:
            continue
        raw_name = _clean_text(name_node.get_text(" ", strip=True))
        name = re.sub(r"\s+", "", raw_name)
        item_text = _clean_text(item.get_text(" ", strip=True))
        evidence = _clean_evidence(item_text.replace(raw_name, "", 1))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "qzld列表li；a姓名；条目剩余文本职务",
            }
        )
    if not records:
        title = _clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
        if title == "502" or "源站不可用" in soup.get_text(" ", strip=True):
            raise RuntimeError("入口页返回502源站不可用，未取得全总领导列表DOM")
        raise RuntimeError("全国总工会全总领导列表未解析到人物记录")
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
