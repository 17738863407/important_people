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
    "rule_id": "0863",
    "page_type": "人物目录详情页",
    "structure_group": "haikou_government_grouped_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "haikou_government_grouped_profiles_v2",
    "leader_region_selector": ".nld",
    "name_selector": "li p a[href]",
    "duty_selector": ".nld > span",
    "detail_link_selector": "li p a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_current_sentence",
        "detail_content_selector": ".main01-rcr3",
        "max_detail_links": 50,
    },
    "risk_flag": "同一人物卡片含图片空链接和姓名链接，只取有姓名文本的最后一个链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def _clean_current_evidence(value: str) -> str:
    """删除固定现任标签、纯句末句号及无期限独立状态标记。"""
    evidence = re.sub(r"^现任\s*", "", _clean_text(value))
    marker = r"(?:（(?:兼|挂职|主持日常工作|主持工作)）|\((?:兼|挂职|主持日常工作|主持工作)\)|[<＜](?:兼|挂职)[>＞])"
    evidence = re.sub(marker, "", evidence)
    return re.sub(r"。$", "", evidence).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按市长、副市长、秘书长分组顺序发现详情并提取现任字段。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    groups = soup.select(page_rule["leader_region_selector"])
    if not groups:
        return []

    entry_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for group in groups:
        duty_node = group.find("span")
        if duty_node is None or not _clean_text(duty_node.get_text(" ", strip=True)):
            continue
        for item in group.select("li"):
            name_links = [
                link
                for link in item.select("p a[href]")
                if _clean_text(link.get_text(" ", strip=True))
            ]
            if not name_links:
                continue
            link = name_links[-1]
            name = re.sub(
                r"[\s\u2000-\u200b\u3000\xa0]+",
                "",
                link.get_text(" ", strip=True),
            )
            if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                continue
            seen.add(name)
            candidates.append((name, urljoin(entry_url, link["href"])))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": entry_url})
    records: list[object] = []
    for name, detail_url in candidates:
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        content = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        detail_text = _clean_text(content.get_text(" ", strip=True)) if content else ""
        evidence_match = re.search(r"现任.*?(?=。|分\s*工\s*：|$)", detail_text)
        if evidence_match is None:
            raise RuntimeError(f"人物详情基本信息缺少可验证的现任职务依据：{name}")
        evidence = re.sub(
            r"[\s\u2000-\u200b\u3000\xa0]+",
            "",
            evidence_match.group(0),
        )
        if "。" in detail_text[evidence_match.end() : evidence_match.end() + 1]:
            evidence += "。"
        evidence = _clean_current_evidence(evidence)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=response.url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
