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
    "rule_id": "4275",
    "page_type": "领导图片卡片详情列表",
    "structure_group": "宁夏社保局领导卡片与简历详情页",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_detail",
    "parser": "page_inline_ningxia_social_insurance_leaders_v1",
    "leader_region_selector": ".zfxxgk_zdgkc ul.leaderlist",
    "name_selector": ".zfxxgk_zdgkc ul.leaderlist p",
    "duty_selector": "详情正文首句的中共党员字段后文本",
    "detail_link_selector": ".zfxxgk_zdgkc ul.leaderlist a[href]",
    "detail_strategy": {"required": True, "mode": "list_link"},
    "risk_flag": "详情首句同时含简历与现职，须以明确的政治面貌字段和句号边界剥离现职，不能把分工写入依据说明。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物卡片顺序提取详情正文首句中的现职字段。"""
    from bs4 import BeautifulSoup
    import requests

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.trust_env = False
    session.headers["User-Agent"] = "Mozilla/5.0"
    rows: list[dict[str, str]] = []
    base_url = final_url or str(page_rule["url"])
    for link in soup.select(".zfxxgk_zdgkc ul.leaderlist a[href]"):
        name_node = link.select_one("p")
        if not name_node:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        detail_url = urljoin(base_url, link["href"])
        try:
            response = session.get(detail_url, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            continue
        response.encoding = response.apparent_encoding or "utf-8"
        detail_soup = BeautifulSoup(response.text, "html.parser")
        body = detail_soup.select_one(".view.TRS_UEDITOR")
        if not body:
            continue
        text = re.sub(r"\s+", "", body.get_text(" ", strip=True))
        first_sentence = text.split("。", 1)[0]
        marker = "中共党员，"
        if not first_sentence.startswith(name + "，") or marker not in first_sentence:
            continue
        duty = first_sentence.split(marker, 1)[1].strip()
        if not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "parser": page_rule["parser"], "selector_summary": "领导卡片链接 + 详情简历首句"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
