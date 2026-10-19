from __future__ import annotations
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1448", "page_type": "人物列表完整页", "structure_group": "机构领导个人简历段落",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "list_direct", "collector": "static_http", "parser": "page_anhui_grain_profile_paragraphs_v2",
    "leader_region_selector": ".j-fontContent.newscontnet", "name_selector": "含个人简历段落冒号后姓名",
    "duty_selector": "同一人物段落完整现任句", "detail_link_selector": "",
    "risk_flag": "正文含个人履历，仅在各个人简历段落内提取完整现任句", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_layout(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"(?<=[\u4e00-\u9fff，、；：])\s+(?=[\u4e00-\u9fff，、；：。])", "", text)


def clean_evidence(value: str) -> str:
    """删除完整现任句的固定标签与纯句末句号。"""
    text = re.sub(r"^现任\s*", "", clean_layout(value))
    return text[:-1].rstrip() if text.endswith("。") else text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".j-fontContent.newscontnet")
    if region is None:
        raise RuntimeError("未定位到粮食和物资储备局机构领导正文")
    rows: list[dict] = []
    for paragraph in region.select("p"):
        text = clean_layout(paragraph.get_text(" ", strip=True))
        name_match = re.search(r"个人简历[:：]\s*([\u4e00-\u9fff·]{2,4})[，,]", text)
        duty_match = re.search(r"现任[^。]*。", text)
        if not name_match or not duty_match:
            continue
        name, evidence = name_match.group(1), clean_evidence(duty_match.group(0))
        rows.append({"organization": page_rule["organization"], "url": page_rule["url"], "name": name,
                     "duty": evidence, "detail_url": "", "evidence": evidence, "confidence": "high",
                     "parser": "page_anhui_grain_profile_paragraphs_v2",
                     "selector_summary": "strategy=custom_parse_page；scope=.j-fontContent.newscontnet；item=含个人简历p；duty=同段完整现任句"})
    if not rows:
        raise RuntimeError("机构领导个人简历段落未抽取到人物")
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
