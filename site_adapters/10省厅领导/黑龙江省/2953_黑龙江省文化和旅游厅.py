from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2953",
    "page_type": "人物接口数据页",
    "structure_group": "hlj_government_leader_api_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "page_inline_hlj_wlt_leader_api_v1",
    "leader_region_selector": "当前栏目channelName=机构领导",
    "name_selector": "data.results[].title",
    "duty_selector": "domainMetaList[LeaderData].resultList[key=post].value",
    "detail_link_selector": "data.results[].url",
    "detail_strategy": {"required": True, "mode": "dynamic_api_url"},
    "risk_flag": "入口页含依申请公开验证码表单，不能把验证码字样误判为防护页；领导数据由公开接口加载",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """确定性清理接口字段中的排版空白。"""
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    return re.sub(r"\s*([、，。；：])\s*", r"\1", text)


def get_channel_identity(final_url: str) -> tuple[str, str, str]:
    """根据规则入口路径动态核对机构领导栏目并返回站点代码和栏目ID。"""
    parsed = urlsplit(final_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or not re.fullmatch(r"c\d+", parts[1]):
        raise RuntimeError("规则入口未包含可识别的栏目代码")
    website_code, channel_code = parts[0], parts[1]
    endpoint = urljoin(final_url, "/common/getChannelList")
    response = requests.get(
        endpoint,
        params={"channelCode": channel_code, "websiteCodeName": website_code},
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    channel = response.json().get("results") or {}
    if str(channel.get("channelName") or "") != "机构领导":
        raise RuntimeError("规则入口对应栏目不是机构领导")
    channel_id = str(channel.get("channelId") or "")
    if not re.fullmatch(r"[0-9a-f]{32}", channel_id):
        raise RuntimeError("机构领导栏目ID无效")
    return website_code, channel_code, channel_id


def extract_post(item: dict[str, object]) -> str:
    """读取领导元数据中的强结构职务字段。"""
    for group in item.get("domainMetaList") or []:
        if str(group.get("domainMetadataCode") or "") != "LeaderData":
            continue
        for field in group.get("resultList") or []:
            if str(field.get("key") or "") == "post":
                return clean_text(field.get("value"))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按公开接口原始数组顺序读取机构领导姓名、职务和详情链接。"""
    del html
    _, _, channel_id = get_channel_identity(final_url)
    endpoint = urljoin(final_url, f"/common/search/{channel_id}")
    response = requests.get(
        endpoint,
        params={
            "_isAgg": "false",
            "_isJson": "true",
            "_pageSize": "100",
            "_template": "index",
            "_rangeTimeGte": "",
            "_channelName": "",
            "page": "1",
        },
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if str(payload.get("channelName") or "") != "机构领导":
        raise RuntimeError("公开接口返回的栏目不是机构领导")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in payload.get("data", {}).get("results", []):
        if str(item.get("channelName") or "") != "机构领导":
            continue
        name = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(item.get("title") or ""))
        evidence = extract_post(item)
        detail_path = str(item.get("url") or "").strip()
        if (
            not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name)
            or not evidence
            or not detail_path
            or name in seen
        ):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": urljoin(final_url, detail_path),
                "evidence": evidence,
                "parser": str(page_rule["parser"]),
                "selector_summary": "api=data.results；name=title；evidence=LeaderData.post；detail=url",
            }
        )

    if not rows:
        raise RuntimeError("公开接口的机构领导数组解析为空")
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
    rows = normalize_inline_rows(page_rule, parse_page("", str(page_rule["url"]), page_rule))
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
