from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2021",
    "page_type": "人物列表完整页",
    "reuse_scope": "single_page",
    "load_mode": "iframe嵌入",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "parser": "page_parse_page",
    "leader_region_selector": "iframe#menuFrame",
    "name_selector": ".provincial-leaders-inner a[href]",
    "duty_selector": ".provincial-leaders-inner a[href]",
    "detail_link_selector": ".provincial-leaders-inner a[href]",
    "detail_strategy": {"required": True, "mode": "person_name_link"},
    "risk_flag": "入口外壳的requests脚本跳转错误，online由Playwright取得iframe；领导数据在iframe原始HTML",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "risk_note": "动态解析menuFrame的src，只读取iframe内provincial-leaders-inner人物链接，不扫描政府公开目录或内设机构。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从入口动态发现机关简介iframe，并解析其中能源局领导列表。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    shell_soup = BeautifulSoup(html, "html.parser")
    frame = shell_soup.select_one("iframe#menuFrame[src]")
    if frame is None:
        raise ValueError("政府信息公开入口未发现menuFrame")
    frame_result = fetch_html_with_strategy(urljoin(final_url, str(frame.get("src", ""))), "raw_http")
    frame_soup = BeautifulSoup(frame_result.html, "html.parser")
    rows: list[dict[str, str]] = []
    for link in frame_soup.select('.provincial-leaders-inner a[href*="../ldfg/"]'):
        raw_text = link.get_text(" ", strip=True).replace("\u3000", " ").replace("\xa0", " ")
        person_match = re.fullmatch(
            r"((?:[\u4e00-\u9fff·]\s*){2,8}?)\s{3,}([\u4e00-\u9fff][^\r\n]+)",
            raw_text,
        )
        if person_match is None:
            raise ValueError(f"领导链接姓名职务结构无法验证：{raw_text[:80]}")
        name = re.sub(r"\s+", "", person_match.group(1))
        duty = re.sub(r"\s+", " ", person_match.group(2)).strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            raise ValueError(f"领导链接姓名或职务字段无效：{raw_text[:80]}")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(frame_result.final_url, str(link.get("href", ""))),
                "evidence": duty,
                "parser": "page_parse_page",
                "selector_summary": "入口=iframe#menuFrame；名单=.provincial-leaders-inner人物链接",
            }
        )
    if not rows:
        raise ValueError("机关简介iframe未发现能源局领导人物链接")
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
