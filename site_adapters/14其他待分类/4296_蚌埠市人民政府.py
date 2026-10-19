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
    "rule_id": "4296",
    "page_type": "dynamic_label_fragment",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "入口页通过站点标签接口异步加载市委、市政府两组领导；仅采集市政府标签。",
    "confidence": "high",
}


def _label_fragment(html: str, base_url: str) -> str:
    """从入口页公开 data-setting 读取当前标签接口并取得其 HTML 片段。"""
    from bs4 import BeautifulSoup
    import requests

    soup = BeautifulSoup(html, "html.parser")
    holder = soup.select_one(".j-label-list[data-setting]")
    if holder is None:
        return ""
    setting = holder.get("data-setting", "")
    file_match = re.search(r"file\s*:\s*'([^']+)'", setting)
    id_match = re.search(r"id\s*:\s*(\d+)", setting)
    if not file_match or not id_match:
        return ""
    payload = {
        "id": id_match.group(1),
        "file": file_match.group(1),
        "labelName": "leaderPositions",
        "length": "50",
        "dateFormat": "MM-dd",
        "target": "_blank",
        "dataType": "HTML",
        "isAllSite": "false",
    }
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        urljoin(base_url, "/site/label/8888"),
        params=payload,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=25,
        verify=False,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    """解析公开标签接口中 #atab3 的市政府领导卡片及其真实详情链接。"""
    from bs4 import BeautifulSoup

    fragment = _label_fragment(html, final_url)
    soup = BeautifulSoup(fragment, "html.parser")
    government = soup.select_one("#atab3")
    if government is None:
        return []
    rows: list[dict[str, str]] = []
    for group in government.select(".leader-main"):
        title = group.select_one(".fltit")
        duty = title.get_text(" ", strip=True) if title else ""
        for link in group.select(".ldrw a[href]"):
            name = link.get_text(" ", strip=True)
            if name and duty:
                rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, link["href"])})
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
