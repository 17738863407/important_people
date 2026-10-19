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


PAGE_RULE = {
    "rule_id": "2172",
    "page_type": "静态人物列表页",
    "structure_group": "中国红十字会领导机构标题人物链接",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_redcross_org_cn_leader_links_v3",
    "leader_region_selector": "section.w1200.m-con-01 #ListInfo",
    "name_selector": "li.page_t > a[title]标题末尾姓名",
    "duty_selector": "li.page_t > a[title]标题前部职务",
    "detail_link_selector": "li.page_t > a[href][title]",
    "risk_flag": "同一列表末尾含第十二届各委员会机构链接，须按标题末尾姓名强结构排除",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(value: str) -> str:
    """统一半角、全角及不换行空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_name_and_duty(text: str) -> tuple[str, str] | None:
    """从“完整职务＋姓名＋人物注记”链接标题中拆分姓名和职务。"""
    value = normalize_space(text)
    matched = re.fullmatch(
        r"(?P<duty>中国红十字会.*?\S)\s+"
        r"(?P<name>[\u4e00-\u9fff·]{2,4})"
        r"(?P<notes>(?:[（(][^）)]*[）)])*)",
        value,
    )
    if not matched:
        return None
    return matched.group("name"), matched.group("duty")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """解析浏览器渲染后的红十字会领导机构人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("section.w1200.m-con-01")
    if scope is None:
        raise RuntimeError("未定位到中国红十字会领导机构区")

    rows: list[dict] = []
    for link in scope.select("#ListInfo > li.page_t > a[href][title]"):
        title = normalize_space(str(link.get("title") or ""))
        if "第十二届" in title:
            continue
        parsed = parse_name_and_duty(title)
        if parsed is None:
            continue
        name, evidence = parsed
        rows.append(
            {
                "organization": page_rule["organization"],
                "url": page_rule["url"],
                "name": name,
                "duty": evidence,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
                "evidence": evidence,
                "confidence": "high",
                "parser": "page_redcross_org_cn_leader_links_v3",
                "selector_summary": (
                    "strategy=custom_parse_page；scope=section.w1200.m-con-01 #ListInfo；"
                    "fields=li.page_t直属链接标题前部职务与末尾姓名；exclude=第十二届机构链接"
                ),
            }
        )
    if not rows:
        raise RuntimeError("浏览器DOM未抽取到中国红十字会领导人物")
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
