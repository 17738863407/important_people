from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def extract_duty(content: object, name: str) -> tuple[str, str]:
    """从当前人物正文中提取分工语句之前的原始职务文本。"""
    role_pattern = re.compile(r"书记|主任|副主任|巡视员|负责人")
    responsibility_pattern = re.compile(r"(?=主持|分管|负责|协助|联系)")

    for block in content.find_all(["p", "div"], recursive=False):
        block_text = clean_text(block.get_text(" ", strip=True))
        if not block_text or not role_pattern.search(block_text):
            continue

        duty_source = ""
        for child in block.find_all(recursive=False):
            child_text = clean_text(child.get_text(" ", strip=True))
            if role_pattern.search(child_text):
                duty_source = child_text
                break
        if not duty_source:
            duty_source = block_text

        evidence = responsibility_pattern.split(duty_source, maxsplit=1)[0].strip()
        duty = evidence.strip(" ，,。；;：:")
        if duty and role_pattern.search(duty):
            return duty, evidence
    raise ValueError(f"{name}详情页人物正文未找到可靠职务节点")


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按目录原始顺序抓取人物详情页，并排除“主持、分管”等分工文本。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    directory = soup.select_one("div.listCont > ul.commonlist26")
    if directory is None:
        raise ValueError("未找到领导目录 div.listCont > ul.commonlist26")

    base_url = final_url or str(page_rule.get("url", ""))
    links: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in directory.select("li > a[href]"):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if not href or href.lower().startswith(("javascript:", "mailto:", "#")):
            continue
        detail_url = urljoin(base_url, href)
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        links.append((name, detail_url))

    if not links:
        raise ValueError("领导目录未发现有效人物详情链接")

    rows: list[dict[str, str]] = []
    selector_summary = (
        "strategy=custom_parse_page；leader=div.listCont > ul.commonlist26；"
        "name=li > a[href]；duty=div.list_con div.content直接内容块；"
        "detail=li > a[href]；collector=chrome_cdp"
    )
    for name, detail_url in links:
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="chrome")
        except Exception as error:
            raise RuntimeError(f"{name}详情页采集失败：{error}") from error

        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        content = detail_soup.select_one("div.list_con div.content")
        if content is None:
            raise ValueError(f"{name}详情页未找到 div.list_con div.content")
        duty, evidence = extract_duty(content, name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": evidence,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": "page_inline_cdwl_leader_detail_v1",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0182",
    "page_type": "人物目录详情页",
    "structure_group": "cdwl_leader_directory_detail",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "list_to_detail",
    "collector": "browser_dom",
    "parser": "page_inline_cdwl_leader_detail_v1",
    "leader_region_selector": "div.listCont > ul.commonlist26",
    "name_selector": "li > a[href]",
    "duty_selector": "div.list_con div.content > p, div.list_con div.content > div",
    "detail_link_selector": "li > a[href]",
    "detail_strategy": {"required": False, "mode": "inline_detail_fetch"},
    "risk_flag": "站点HTTP请求返回412且无头Playwright结果无效；详情正文职务与分工相邻，需在人物正文内按明确分工起始词裁剪",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.listCont > ul.commonlist26",
            "name_selector": "li > a[href]",
            "duty_selector": "div.list_con div.content > p, div.list_con div.content > div",
            "detail_link_selector": "li > a[href]",
        },
        "api": {
            "enabled": False,
            "reason": "当前领导目录及详情正文均由浏览器渲染DOM提供，未发现可复现结构化接口",
        },
        "migration": {
            "source": "failed_script_v3_task7",
            "verified_status": "online_verified_20260808",
            "behavior_changed": True,
        },
    },
}


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
