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
    "rule_id": "3071",
    "page_type": "人物列表完整页",
    "structure_group": "chengdu_petition_protected_leader_page",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_to_detail",
    "collector": "browser_dom_list_and_detail",
    "parser": "chengdu_petition_protected_page_v2",
    "leader_region_selector": "ul.sxgk_list > li.clearFix",
    "name_selector": "div.text h2 > a",
    "duty_selector": "详情页 p.MsoNormal 中姓名后的首个现职句",
    "detail_link_selector": "div.text h2 > a[href*='content_']",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["ul.sxgk_list"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "custom_list_to_detail",
        "detail_link_selector": "div.text h2 > a[href*='content_']",
        "max_detail_links": 20,
    },
    "risk_flag": "入口和详情页采用项目独立Chrome CDP通道；详情页简介第一句为人口学信息，只提取其后的现职句，排除职责段",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "当前入口具有稳定 sxgk_list 列表，人物链接动态来自列表，详情页具有稳定 MsoNormal 简介段",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_name(value: str) -> str:
    """清理姓名中的排版空白和零宽字符。"""
    return re.sub(r"[\s\u200b-\u200d\ufeff]+", "", value or "").strip()


def clean_sentence(value: str) -> str:
    """清理已经定位到的现职句，仅整理排版字符和句末标点。"""
    text = " ".join(
        str(value or "")
        .replace("\u3000", " ")
        .replace("\xa0", " ")
        .replace("\u200b", " ")
        .split()
    )
    text = re.sub(
        r"(?<=[\u4e00-\u9fff\u3400-\u4dbf])\s+(?=[\u4e00-\u9fff\u3400-\u4dbf])",
        "",
        text,
    )
    return text.rstrip("。；; ")


def extract_detail_evidence(html: str, expected_name: str) -> str:
    """校验详情页姓名，并从人物简介段中提取人口学信息后的首个现职句。"""
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one("h1")
    title = clean_name(title_node.get_text(" ", strip=True) if title_node else "")
    if expected_name not in title:
        raise RuntimeError(f"详情页标题与列表姓名不匹配：列表={expected_name}，标题={title or '<空>'}")

    paragraphs = soup.select("#detail p")
    for index, paragraph in enumerate(paragraphs):
        paragraph_text = " ".join(paragraph.get_text(" ", strip=True).split())
        if not clean_name(paragraph_text).startswith(expected_name):
            continue
        following_text = " ".join(
            item.get_text(" ", strip=True) for item in paragraphs[index : index + 3]
        )
        current_match = re.search(r"现任\s*([^。]+)。", following_text)
        if current_match is not None:
            evidence = clean_sentence(current_match.group(1))
            if evidence:
                return evidence

        sentences = [clean_sentence(item) for item in re.split(r"[。]", paragraph_text)]
        sentences = [item for item in sentences if item]
        if len(sentences) < 2:
            raise RuntimeError(f"{expected_name} 简介段未包含姓名信息之后的现职句")
        evidence = sentences[1]
        if evidence.startswith(("主持", "负责", "分管", "联系")):
            raise RuntimeError(f"{expected_name} 简介段第二句属于职责说明，未取得可靠现职句")
        if not re.search(r"书记|局长|主任|组长|委员|干部|巡视员|调研员|副部长", evidence):
            raise RuntimeError(f"{expected_name} 简介段第二句缺少可验证职务词：{evidence}")
        return evidence
    raise RuntimeError(f"{expected_name} 详情页未找到以姓名开头的 #detail 简介段")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按入口页人物顺序动态进入详情页，提取完整现职句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select(
        "ul.sxgk_list > li.clearFix div.text h2 > "
        "a[href*='/xinfang/c142230/'][href*='content_']"
    )
    if not links:
        raise RuntimeError("入口页未找到领导介绍列表 ul.sxgk_list")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in links:
        name = clean_name(link.get_text(" ", strip=True))
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff\u3400-\u4dbf·]{2,8}", name):
            raise RuntimeError(f"领导姓名格式异常：{name or '<空>'}")
        if not href:
            raise RuntimeError(f"{name} 缺少可验证的详情页链接")
        if name in seen_names:
            raise RuntimeError(f"入口页领导姓名重复：{name}")
        seen_names.add(name)

        detail_url = urljoin(final_url or str(page_rule.get("url") or ""), href)
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="chrome")
            evidence = extract_detail_evidence(detail_result.html, name)
        except Exception as error:
            raise RuntimeError(f"{name} 详情页采集或解析失败：{error}") from error
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_parse_page",
                "selector_summary": "sxgk_list列表；h2链接姓名；详情p.MsoNormal简介第二句",
            }
        )
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
