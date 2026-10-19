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
    "rule_id": "0155",
    "page_type": "人物列表完整页",
    "structure_group": "海洋咨询中心姓名分隔线职务段落组",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "CcsoaLeaderTextPairsParser_v2",
    "leader_region_selector": "#txtc_con_11_3",
    "name_selector": "姓名段落",
    "duty_selector": "姓名后的非空非分隔线职务段落",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口HTML由外部CDN脚本动态写入正文；必须使用在线渲染DOM，并在最小领导容器内按姓名、分隔线、职务顺序配对",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析动态正文中的“姓名—分隔线—职务”段落组。"""
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = [
        _clean_text(paragraph.get_text(" ", strip=True))
        for paragraph in soup.select("#txtc_con_11_3 p")
    ]
    paragraphs = [text for text in paragraphs if text]
    if not paragraphs:
        raise RuntimeError("未找到海洋咨询中心领导介绍动态正文")
    records: list[dict] = []
    current_name = ""
    seen_names: set[str] = set()
    for text in paragraphs:
        if text == "—":
            continue
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", text):
            current_name = text
            continue
        if current_name and any(keyword in text for keyword in ("主任", "党委", "纪委")):
            if current_name not in seen_names:
                seen_names.add(current_name)
                records.append(
                    {
                        "name": current_name,
                        "duty": text.strip("；。"),
                        "evidence": text,
                        "detail_url": "",
                        "parser": PAGE_RULE["parser"],
                        "selector_summary": "#txtc_con_11_3 p；姓名—分隔线—职务顺序配对",
                    }
                )
            current_name = ""
    if not records:
        raise RuntimeError("领导介绍动态正文未解析到人物记录")
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
