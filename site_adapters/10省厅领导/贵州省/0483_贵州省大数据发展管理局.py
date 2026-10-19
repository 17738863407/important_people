from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0483",
    "page_type": "人物列表完整页",
    "structure_group": "gz_bigdata_profile_fields_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#Left_Nav",
    "name_selector": "#Left_Nav a[href][title]",
    "duty_selector": ".ldzc_left担任职务字段",
    "detail_link_selector": "#Left_Nav a[href][title]",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "个人履历含历任经历和现任句；只读取详情顶部担任职务强字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*([、，,；;：:])\s*", r"\1", text)


def _clean_duty_evidence(value: str) -> str:
    """仅删除无期限的独立挂职标记，保留带期限的挂职信息。"""
    text = re.sub(r"(?:<\s*挂职\s*>|[（(]\s*挂职\s*[）)])", "", _clean_text(value))
    return _clean_text(text).rstrip("，,；;。")


def _extract_profile_fields(html: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one(".ldzc_left") or soup.select_one(".ldzc")
    if content is None:
        return "", ""
    text = _clean_text(content.get_text(" ", strip=True))
    name_match = re.search(r"姓\s*名[：:]\s*([\u4e00-\u9fff·]{2,8})", text)
    duty_match = re.search(r"担任职务[：:]\s*(.*?)(?:领导分工[：:]|个人履历|$)", text)
    name = re.sub(r"\s+", "", _clean_text(name_match.group(1))) if name_match else ""
    duty = _clean_duty_evidence(duty_match.group(1)) if duty_match else ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按左侧领导导航顺序在线请求详情并读取姓名、担任职务字段。"""
    import requests
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    entry_url = final_url or page_rule["url"]
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("#Left_Nav a[href][title]"):
        nav_name = re.sub(r"\s+", "", _clean_text(link.get("title") or link.get_text("", strip=True)))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", nav_name) is None or nav_name in seen:
            continue
        detail_url = urljoin(entry_url, str(link.get("href", "")))
        try:
            response = session.get(detail_url, timeout=25)
            response.raise_for_status()
        except requests.RequestException:
            continue
        response.encoding = response.apparent_encoding or response.encoding
        name, duty = _extract_profile_fields(response.text)
        if name != nav_name or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": response.url,
            }
        )

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
