from __future__ import annotations

import json
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


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def read_embedded_array(html: str, group_key: str) -> list[dict[str, object]]:
    """从页面内嵌 zfldData 对象读取指定领导分组数组。"""
    match = re.search(rf"['\"]{re.escape(group_key)}['\"]\s*:\s*", html)
    if not match:
        return []
    value, _ = json.JSONDecoder().raw_decode(html[match.end():])
    return value if isinstance(value, list) else []


def extract_duty(item: dict[str, object]) -> str:
    """优先采用页面展示标题，回退到接口原职务字段或当前简介句。"""
    from bs4 import BeautifulSoup

    show_title = BeautifulSoup(str(item.get("showTitle") or ""), "html.parser")
    first_paragraph = show_title.find("p")
    duty = clean_text(first_paragraph.get_text(" ", strip=True) if first_paragraph else "")
    if duty:
        return duty.rstrip("。；; ")
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    duty = clean_text(str(metadata.get("Post") or ""))
    if duty:
        return duty.rstrip("。；; ")
    profile = clean_text(str(metadata.get("ldjl") or ""))
    current_match = re.search(r"现任([^。]+)", profile)
    return clean_text(current_match.group(1)).rstrip("。；; ") if current_match else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按页面 zfldData 的市长、副市长、秘书长数组顺序提取。"""
    source = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for group_key in ("sz", "fsz", "msz"):
        for item in read_embedded_array(html, group_key):
            name = clean_text(str(item.get("title") or "")).replace(" ", "")
            duty = extract_duty(item)
            urls = item.get("urls")
            url_data = json.loads(urls) if isinstance(urls, str) and urls else {}
            detail = str(url_data.get("pc") or item.get("redirectUrl") or "")
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
                continue
            rows.append({
                "name": name,
                "duty": "",
                "evidence": duty,
                "detail_url": urljoin(source, detail),
                "confidence": "high",
                "parser": "page_inline_kaifeng_embedded_zfld_data_v1",
            })
    return rows


PAGE_RULE = {
    "rule_id": "3848",
    "page_type": "内嵌JavaScript领导数据",
    "load_mode": "静态HTML直出数据、前端渲染列表",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "embedded_json",
    "parser": "page_inline_kaifeng_embedded_zfld_data_v1",
    "leader_region_selector": ".item.leader",
    "name_selector": "#index-data-sz li, #index-data-fsz li, #index-data-msz li",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "可见列表由页面内嵌zfldData渲染",
    "confidence": "high",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
