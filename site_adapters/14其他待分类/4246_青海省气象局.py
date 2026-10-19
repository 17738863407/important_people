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
    "rule_id": "4246", "page_type": "领导卡片与详情页", "load_mode": "带浏览器请求头的静态 HTML",
    "extract_mode": "card_list", "parser": "page_inline_qh_cma_leaders_v1",
    "leader_region_selector": ".er_right_list_out", "name_selector": ".er_right_list_right span > a",
    "duty_selector": "同卡标题冒号前文本", "detail_link_selector": ".er_right_list_right span > a[href]",
    "detail_strategy": {"required": False, "mode": "person_profile_link"}, "confidence": "high", "filter_policy": "strong_card_structure",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """从“局领导”卡片的当前标题和真实个人链接动态拆分姓名、职务。"""
    from bs4 import BeautifulSoup
    import requests

    session = requests.Session()
    session.trust_env = False
    response = session.get(str(page_rule["url"]), headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36", "Accept-Language": "zh-CN,zh;q=0.9"}, timeout=30, verify=False)
    response.raise_for_status()
    response.encoding = "utf-8"
    rows: list[dict] = []
    for card in BeautifulSoup(response.text, "html.parser").select(".er_right_list_out > .er_right_list"):
        anchor = card.select_one(".er_right_list_right span > a[href]")
        title = "".join(anchor.get_text(" ", strip=True).split()) if anchor else ""
        match = re.fullmatch(r"(.+?)：([\u4e00-\u9fff]{2,8})(（[^）]+）)?", title)
        if match and anchor:
            duty, name, suffix = match.groups()
            if suffix:
                duty = f"{duty}{suffix}"
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(response.url, anchor.get("href"))})
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
