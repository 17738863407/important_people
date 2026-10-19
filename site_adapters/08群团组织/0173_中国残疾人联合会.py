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
    "rule_id": "0173",
    "page_type": "人物列表完整页",
    "structure_group": "中国残联名誉主席卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "requests_raw",
    "parser": "CdpfHonoraryChairCardParser_v2",
    "leader_region_selector": "div.sub_right div.pageList div.subLeaderBox01",
    "name_selector": "h3末尾姓名",
    "duty_selector": "h3姓名之前的原始职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "online会误跟随无障碍脚本跳转；raw_http可取得权威原始页面，职务不得删除机构前缀",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """从名誉主席卡片标题拆分完整原始职务与末尾姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for card in soup.select("div.sub_right div.pageList div.subLeaderBox01"):
        title_node = card.select_one("h3")
        if title_node is None:
            continue
        title = _clean_text(title_node.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?)\s+([\u4e00-\u9fff·]{2,5})", title)
        if match is None:
            continue
        evidence = _clean_text(match.group(1))
        name = re.sub(r"\s+", "", match.group(2))
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "名誉主席subLeaderBox01卡片；h3末尾姓名；此前文本为完整职务",
            }
        )
    if not records:
        raise RuntimeError("中国残联名誉主席卡片未解析到人物记录")
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
