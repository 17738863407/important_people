from __future__ import annotations

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


PAGE_RULE = {
    "rule_id": "1444",
    "page_type": "人物接口数据页",
    "structure_group": "hlj_government_leader_api_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "page_inline_hlj_grain_leader_api_v1",
    "leader_region_selector": "公开接口channelName=局领导",
    "name_selector": "data.results[].title",
    "duty_selector": "data.results[].content首个完整句",
    "detail_link_selector": "data.results[].url",
    "detail_strategy": {"required": True, "mode": "dynamic_api_url"},
    "api": {
        "enabled": True,
        "path": "/common/search/af225a514fad45fdbbe536da5698efda",
        "params": {
            "_isAgg": "false",
            "_isJson": "true",
            "_pageSize": "100",
            "_template": "index",
            "_rangeTimeGte": "",
            "_channelName": "",
            "page": "1",
        },
        "data_path": "data.results",
    },
    "risk_flag": "入口页含依申请公开验证码表单，不能把验证码字样误判为防护页；领导数据由公开接口加载",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """确定性清理接口正文中的HTML与排版空白。"""
    text = BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", text).strip()
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    return re.sub(r"\s*([、，。；：])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按公开接口原始数组顺序读取局领导姓名、职务首句和详情链接。"""
    del html
    api_rule = page_rule["api"]
    api_url = urljoin(final_url, str(api_rule["path"]))
    response = requests.get(
        api_url,
        params=dict(api_rule["params"]),
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if str(payload.get("channelName") or "") != "局领导":
        raise RuntimeError("公开接口返回的栏目不是局领导")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in payload.get("data", {}).get("results", []):
        if str(item.get("channelName") or "") != "局领导":
            continue
        name = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(item.get("title") or ""))
        content = clean_text(item.get("contentHtml") or item.get("content") or "")
        sentence = re.match(r"(.+?。)", content)
        detail_url = urljoin(final_url, str(item.get("url") or "").strip())
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or sentence is None or name in seen:
            continue
        seen.add(name)
        evidence = sentence.group(1).removesuffix("。").strip()
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": str(page_rule["parser"]),
                "selector_summary": "api=data.results；name=title；evidence=content首句；detail=url",
            }
        )

    if not rows:
        raise RuntimeError("公开接口的局领导数组解析为空")
    return rows


def main(output_dir: Path | None = None) -> None:
    """直接调用公开领导接口，避开入口页表单中的验证码误判。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.business_sources import apply_business_source
    from crawler_core.exporter import export_records
    from crawler_core.runner import (
        build_output_name,
        normalize_inline_rows,
        normalize_record_source_urls,
        prepare_records_for_export,
    )

    page_rule = apply_business_source(PAGE_RULE.copy())
    rows = normalize_inline_rows(
        page_rule,
        parse_page("", str(page_rule["url"]), page_rule),
    )
    normalize_record_source_urls(page_rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        row.script_sequence = str(page_rule["rule_id"]).zfill(4)
    target_dir = output_dir or (project_dir / "outputs")
    output_path = target_dir / build_output_name(str(page_rule["rule_id"]), str(page_rule["organization"]))
    export_records(output_path, rows)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
