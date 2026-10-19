from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0938',
 'page_type': '人物列表完整页',
 'structure_group': 'jiangxi_health_embedded_wld_json',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_jiangxi_health_three_groups_v3',
 'leader_region_selector': 'script',
 'name_selector': 'wld[].title',
 'duty_selector': 'wld[].keywords',
 'detail_link_selector': 'wld[].redirectUrl',
 'detail_strategy': {'required': False,
                     'mode': 'none'},
 'risk_flag': '按页面顺序解析委领导、委直属单位厅级领导、二级巡视员三个严格数组；缺少keywords职务时回查JSON提供的官方详情页',
 'confidence': 'high'}


def clean_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_evidence(value: str, name: str) -> str:
    """按已提取姓名或明确任职年月句动态保留其中的完整职务。"""
    evidence = clean_text(value)
    name_parts = re.split(r"[，,]", evidence, maxsplit=1)
    if len(name_parts) == 2 and clean_text(name_parts[0]) == name:
        return re.sub(r"。$", "", clean_text(name_parts[1])).strip()
    appointment = re.match(
        r"^\d{4}年(?:\d{1,2}月)?[，,]?\s*任\s*(?P<duty>.+?)。?$",
        evidence,
    )
    if appointment:
        return clean_text(appointment.group("duty"))
    return ""


def extract_js_array(source: str, key: str) -> list[dict[str, object]]:
    key_match = re.search(rf"['\"]{re.escape(key)}['\"]\s*:", source)
    if not key_match:
        return []
    start = source.find("[", key_match.end())
    if start < 0:
        return []

    depth = 0
    in_string = False
    quote = ""
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
            continue
        if char in ('"', "'"):
            in_string = True
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return json.loads(source[start:index + 1])
    return []


def extract_detail_evidence(detail_url: str, group_key: str) -> str:
    """从JSON动态提供的详情页提取最新一条明确任职原文。"""
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        detail_url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145 Safari/537.36"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    content = soup.select_one(".leader_txt_content")
    if content is None:
        raise RuntimeError(f"详情页缺少leader_txt_content：{detail_url}")

    group_markers = {
        "wzsdwtjld": ("党委书记", "院长"),
        "ejxsy": ("巡视员",),
    }
    markers = group_markers[group_key]
    text = clean_text(content.get_text(" ", strip=True))
    candidates = [
        clean_text(sentence) + "。"
        for sentence in re.split(r"。", text)
        if "任" in sentence and any(marker in sentence for marker in markers)
    ]
    if not candidates:
        raise RuntimeError(f"详情页未找到当前组的明确任职句：{detail_url}")
    return candidates[-1]


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按在线页面三个人物分组及各组数组原序解析。"""
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for group_key in ("wld", "wzsdwtjld", "ejxsy"):
        items = extract_js_array(html, group_key)
        if not items:
            raise RuntimeError(f"在线页面未解析出{group_key}数组")
        for item in items:
            name = clean_text(item.get("title"))
            keywords = clean_text(item.get("keywords"))
            detail_path = clean_text(item.get("redirectUrl"))
            detail_url = urljoin(final_url, detail_path) if detail_path else ""
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not detail_url:
                raise RuntimeError(f"{group_key}人物字段不完整：{name}")
            if detail_url in seen_urls:
                continue

            parts = re.split(r"[，,]", keywords, maxsplit=1)
            if len(parts) == 2 and clean_text(parts[0]) == name and clean_text(parts[1]):
                evidence = keywords
            elif group_key == "wld":
                raise RuntimeError(f"wld姓名与keywords结构不一致：{name} / {keywords}")
            else:
                evidence = extract_detail_evidence(detail_url, group_key)

            cleaned_evidence = clean_evidence(evidence, name)
            if not cleaned_evidence:
                raise RuntimeError(f"依据说明未能按姓名或明确任职年月拆分：{name} / {evidence}")

            seen_urls.add(detail_url)
            rows.append(
                {
                    "order": str(len(rows) + 1),
                    "name": name,
                    "duty": cleaned_evidence,
                    "detail_url": detail_url,
                    "evidence": cleaned_evidence,
                    "confidence": "high",
                    "parser": "page_inline_jiangxi_health_three_groups_v3",
                }
            )
    if not rows:
        raise RuntimeError("在线页面未解析出三组领导数组")
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
