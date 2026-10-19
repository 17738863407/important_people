from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def clean_text(value: str) -> str:
    """清理正文排版空白，不改变现任句语义。"""
    text = (value or "").replace("\xa0", " ").replace("\u3000", " ")
    text = " ".join(text.split())
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    text = re.sub(r"\s+([，。；：、（）])", r"\1", text)
    return re.sub(r"([，。；：、（）])\s+", r"\1", text)


def clean_name(value: str) -> str:
    """移除姓名字符间的纯排版空格。"""
    return re.sub(r"\s+", "", value or "")


def is_hidden(node: Tag) -> bool:
    """排除节点及祖先明确隐藏的备用 DOM。"""
    current: Tag | None = node
    while current is not None:
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        style = re.sub(r"\s+", "", str(current.get("style", "")).lower())
        if "display:none" in style or "visibility:hidden" in style:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def same_origin(reference_url: str, candidate_url: str) -> bool:
    reference = urlsplit(reference_url)
    candidate = urlsplit(candidate_url)
    return (reference.scheme, reference.netloc) == (candidate.scheme, candidate.netloc)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导分工目录顺序逐详情提取完整现任句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "lxml")
    directory = soup.select_one(".con-right .default_pgContainer")
    candidates: list[tuple[str, str]] = []
    if directory is not None:
        for anchor in directory.select(":scope > li > a[href]"):
            if not is_hidden(anchor):
                candidates.append((anchor.get_text(" ", strip=True), str(anchor.get("href", ""))))
    else:
        datastore_container = soup.find(id="275256")
        datastore = datastore_container.find("script") if datastore_container else None
        datastore_html = str(datastore or "")
        for href, raw_name in re.findall(
            r"<a\s+href=['\"]([^'\"]*art_71689_\d+\.html)['\"][^>]*>(.*?)</a>",
            datastore_html,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            candidates.append((BeautifulSoup(raw_name, "lxml").get_text(" ", strip=True), href))
    if not candidates:
        raise RuntimeError("未找到领导分工目录中的人物链接")

    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for raw_name, raw_href in candidates:
        directory_name = clean_name(raw_name)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", directory_name) or directory_name in seen_names:
            continue
        detail_url = urljoin(final_url, raw_href)
        detail_path = urlsplit(detail_url).path
        if not same_origin(final_url, detail_url) or not re.fullmatch(
            r"/art/\d{4}/\d{1,2}/\d{1,2}/art_71689_\d+\.html",
            detail_path,
        ):
            raise RuntimeError(f"{directory_name}详情路径不符合领导分工栏目结构")

        fetch_result = fetch_html_with_strategy(detail_url, strategy="requests", timeout=30)
        detail_soup = BeautifulSoup(fetch_result.html, "lxml")
        title_node = detail_soup.select_one(".con > p.con-title")
        detail_name = clean_name(title_node.get_text(" ", strip=True) if title_node else "")
        if detail_name != directory_name:
            raise RuntimeError(f"目录姓名与详情标题不一致：{directory_name}/{detail_name or '空'}")

        evidence = ""
        for paragraph in detail_soup.select(".con .main-txt p"):
            if is_hidden(paragraph):
                continue
            paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
            if directory_name not in paragraph_text:
                continue
            match = re.search(r"现任[^。]*。", paragraph_text)
            if match:
                evidence = re.sub(
                    r"^现任(?:职务)?(?:\s*[：:]\s*)?\s*",
                    "",
                    match.group(0),
                    count=1,
                )
                break
        if not evidence:
            raise RuntimeError(f"{directory_name}详情正文未找到可回指的完整现任句")

        seen_names.add(directory_name)
        records.append(
            {
                "name": directory_name,
                "duty": evidence,
                "detail_url": fetch_result.final_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": "page_inline_jiangsu_healthcare_leader_details_v1",
            }
        )
    return records


PAGE_RULE = {
    "rule_id": "3126",
    "page_type": "人物目录详情页",
    "structure_group": "jiangsu_healthcare_rendered_leader_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_jiangsu_healthcare_leader_details_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".con-right .default_pgContainer",
    "name_selector": ":scope > li > a[href]",
    "duty_selector": ".con .main-txt p 内完整现任句",
    "detail_link_selector": ":scope > li > a[href]",
    "risk_flag": "入口原始HTML的XML数据区提供人物目录；详情正文的负责、分管说明不得进入主职务依据",
    "confidence": "high",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
