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
    "rule_id": "3074",
    "page_type": "人物目录详情页",
    "structure_group": "xining_government_directory_fields_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xining_government_directory_fields_v2",
    "leader_region_selector": ".content-zfld .tabItem",
    "name_selector": ".tab1-ch1-box1 p.name, .tab1-item-ch2 li a[href] > p",
    "duty_selector": ".box2_ch .view p strong",
    "detail_link_selector": ".tab1-ch1-box2 a.btn[href], .tab1-item-ch2 li a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_labeled_fields",
        "detail_content_selector": ".box2_ch .view",
        "max_detail_links": 30,
    },
    "risk_flag": "入口卡片仅给分组简职，完整职务位于详情页现任职务字段；不得人为添加机构前缀",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：:（）()])", r"\1", text)


def _clean_name(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def _labeled_field(scope: object, label: str) -> str:
    for paragraph in scope.select("p"):
        strong = paragraph.select_one("strong")
        if strong is None:
            continue
        strong_text = _clean_text(strong.get_text(" ", strip=True)).rstrip("：:")
        if strong_text != label:
            continue
        full_text = _clean_text(paragraph.get_text(" ", strip=True))
        return re.sub(rf"^{re.escape(label)}\s*[：:]\s*", "", full_text).strip()
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按入口卡片顺序逐页读取姓名与现任职务强结构字段。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    mayor_label = region.select_one(".tab1-ch1-box1 p.name")
    mayor_link = region.select_one(".tab1-ch1-box2 a.btn[href]")
    if mayor_label is not None and mayor_link is not None:
        mayor_name = _clean_name(
            re.sub(r"^市长[：:]", "", _clean_text(mayor_label.get_text(" ", strip=True)))
        )
        candidates.append((mayor_name, urljoin(entry_url, mayor_link["href"])))
    for link in region.select(".tab1-item-ch2 li a[href]"):
        label_node = link.select_one(":scope > p")
        label = _clean_text(label_node.get_text(" ", strip=True)) if label_node else ""
        name = _clean_name(label.split("：", 1)[-1]) if "：" in label else ""
        candidates.append((name, urljoin(entry_url, link["href"])))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": entry_url})
    records: list[object] = []
    seen: set[str] = set()
    for expected_name, detail_url in candidates:
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", expected_name) or expected_name in seen:
            continue
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        profile = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        if profile is None:
            raise RuntimeError(f"详情页缺少个人简历字段：{expected_name}")
        profile_name = _clean_name(_labeled_field(profile, "姓名"))
        evidence = _clean_text(_labeled_field(profile, "现任职务"))
        if profile_name != expected_name or not evidence:
            raise RuntimeError(
                f"目录与详情字段无法核对：{expected_name} -> {profile_name or '空'}"
            )
        seen.add(expected_name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=profile_name,
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
