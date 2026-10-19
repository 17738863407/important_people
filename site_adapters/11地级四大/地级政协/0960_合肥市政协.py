from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0960",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "iframe_url": (
        "http://www.hfszx.org.cn/hfzx/web/ifrm_leader.jsp?"
        "strColId=1535617334628001&strWebsiteId=1354153871125000"
    ),
    "leader_region_selector": "dl.council-list.council-lead",
    "person_selector": "dd.leadmore9 > p > span",
    "risk_flag": "入口为栏目框架，领导名单由同站专用iframe承载",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩iframe中的排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """在线读取领导iframe，并按可见人物span顺序拆分姓名和职务。"""
    from crawler_core.dynamic_leader_extractor import split_name_duty
    from crawler_core.fetcher import fetch_html_with_strategy

    iframe_result = fetch_html_with_strategy(
        page_rule["iframe_url"],
        strategy="raw_http",
        timeout=30,
    )
    soup = BeautifulSoup(iframe_result.html, "lxml")
    regions = soup.select(page_rule["leader_region_selector"])
    if not regions:
        raise RuntimeError("未找到政协领导iframe名单区域")

    rows: list[dict] = []
    seen: set[str] = set()
    for region in regions:
        for node in region.select(page_rule["person_selector"]):
            source_text = clean_text(node.get_text(" ", strip=True))
            name, duty = split_name_duty(source_text)
            if name.endswith("市") and duty.startswith("委"):
                name = name[:-1]
                duty = "市" + duty
            name = re.sub(r"\s+", "", name)
            duty = clean_text(duty)
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty:
                raise RuntimeError(f"无法拆分iframe人物文本：{source_text}")
            if name in seen:
                continue
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "confidence": "high",
                    "parser": "page_inline_hefei_cppcc_iframe_v1",
                    "selector_summary": (
                        "iframe=ifrm_leader.jsp；"
                        "person=dl.council-list.council-lead dd.leadmore9 > p > span"
                    ),
                }
            )
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
