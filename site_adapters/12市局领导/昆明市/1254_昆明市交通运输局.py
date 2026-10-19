from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1254",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_transport_paragraph_pairs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_transport_paragraph_pairs_v2",
    "leader_region_selector": ".content p",
    "name_selector": ".content p",
    "duty_selector": ".content p",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "max_detail_links": 0,
    },
    "risk_flag": "部分人物的职务和姓名分为相邻段落，必须保持段落顺序一一配对",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_duty(value: str) -> str:
    """归一化职务内部中文标点附近的确定性排版空格。"""
    return re.sub(r"\s*([、，])\s*", r"\1", clean_text(value))


def is_duty_text(value: str) -> bool:
    return bool(re.search(r"党组|书记|局长|成员|邮政管理局|民航发展局|轨道发展局", value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析同段或相邻两段形式的职务姓名，保留网页原始顺序。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".content") or soup
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    pending_duty = ""
    for paragraph in content.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        compact_name = re.sub(r"\s+", "", text)
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", compact_name) and pending_duty:
            key = (compact_name, pending_duty)
            if key not in seen:
                seen.add(key)
                rows.append(
                    {
                        "name": compact_name,
                        "duty": pending_duty,
                        "detail_url": "",
                        "evidence": pending_duty,
                        "confidence": "high",
                        "parser": page_rule["parser"],
                    }
                )
            pending_duty = ""
            continue

        match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff·]{2,5})", text)
        if match and is_duty_text(match.group("duty")):
            name = match.group("name")
            duty = clean_duty(match.group("duty"))
            key = (name, duty)
            if key not in seen:
                seen.add(key)
                rows.append(
                    {
                        "name": name,
                        "duty": duty,
                        "detail_url": "",
                        "evidence": duty,
                        "confidence": "high",
                        "parser": page_rule["parser"],
                    }
                )
            pending_duty = ""
            continue
        pending_duty = clean_duty(text) if is_duty_text(text) else ""
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
