from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3321",
    "page_type": "现任领导接口分组页",
    "structure_group": "zhzjs_now_duties_api_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态JSON接口",
    "fetch_mode": "raw_http",
    "extract_mode": "field_pair",
    "collector": "requests",
    "parser": "inline_parse_page",
    "leader_region_selector": "",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {"include_selectors": [], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "接口按职务分组返回，同一人物可能跨党组和行政职务组重复，按首次出现顺序去重并合并原始分组证据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_text(value: object) -> str:
    """只压缩接口文本中的排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def normalize_name(value: object) -> str:
    """移除姓名字段中的性别括注与排版空白，不改变姓名字符。"""
    name = re.sub(r"[（(][男女][）)]", "", normalize_text(value))
    return re.sub(r"\s+", "", name)


def sort_number(item: object) -> tuple[int, str]:
    """按接口排序号稳定排序，缺失排序号的记录置后。"""
    if not isinstance(item, dict):
        return (10**9, "")
    raw_value = item.get("sortNo")
    try:
        number = int(raw_value)
    except (TypeError, ValueError):
        number = 10**9
    return (number, normalize_text(item.get("id")))


def post_json(session: requests.Session, api_root: str, path: str, payload: dict[str, str]) -> object:
    """请求站点公开接口并校验统一响应状态。"""
    response = session.post(
        urljoin(api_root.rstrip("/") + "/", path.lstrip("/")) + "?token=",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict) or result.get("code") not in (0, "0"):
        raise ValueError(f"接口返回异常：{path}，响应={result!r}")
    return result.get("data")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """动态解析站点实例并按接口原始分组顺序抽取、去重现任领导。"""
    del html, page_rule
    hostname = urlparse(final_url).hostname or ""
    if not hostname:
        raise ValueError(f"无法从入口页解析站点主机名：{final_url}")

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json, text/plain, */*",
            "Referer": final_url,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145 Safari/537.36",
        }
    )
    config_response = session.get(urljoin(final_url, "/static/configOrg.json"), timeout=30)
    config_response.raise_for_status()
    config = config_response.json()
    api_root = normalize_text(config.get("ApiUrl") if isinstance(config, dict) else "")
    if not api_root.startswith(("http://", "https://")):
        raise ValueError("站点配置未提供有效 ApiUrl")

    base_payload = {
        "appCode": "WEBSITE_PC",
        "domainArray": hostname,
        "tenantId": "",
        "websiteId": "",
        "browserId": "",
    }
    tenant_data = post_json(
        session,
        api_root,
        "/basics-boot/jurisdiction/getTenantByDomainArray",
        base_payload,
    )
    if isinstance(tenant_data, dict):
        tenant_id = normalize_text(tenant_data.get("id") or tenant_data.get("tenantId"))
    else:
        tenant_id = normalize_text(tenant_data)
    if not tenant_id:
        raise ValueError("域名解析接口未返回租户标识")

    website_payload = {**base_payload, "tenantId": tenant_id}
    website_data = post_json(
        session,
        api_root,
        "/website-boot/home/getWebsiteByDomainArray",
        website_payload,
    )
    if not isinstance(website_data, dict):
        raise ValueError("网站解析接口未返回网站对象")
    website_id = normalize_text(website_data.get("id") or website_data.get("websiteId"))
    if not website_id:
        raise ValueError("网站解析接口未返回网站标识")

    leaders_data = post_json(
        session,
        api_root,
        "/website-boot/admin/social/listNowDutiesUser",
        {**website_payload, "websiteId": website_id},
    )
    if not isinstance(leaders_data, list):
        raise ValueError("现任领导接口未返回职务分组数组")

    people: dict[str, list[str]] = {}
    for group in sorted(leaders_data, key=sort_number):
        if not isinstance(group, dict):
            continue
        group_title = normalize_text(group.get("title") or group.get("dutiesName") or group.get("name"))
        members = group.get("children") or group.get("userList") or group.get("list") or []
        if not group_title or not isinstance(members, list):
            continue
        for member in sorted(members, key=sort_number):
            if not isinstance(member, dict):
                continue
            raw_name = normalize_text(member.get("userName") or member.get("name"))
            name = normalize_name(raw_name)
            if not name:
                continue
            evidence_name = re.sub(r"\s+", "", raw_name)
            evidence = f"{group_title}：{evidence_name}"
            evidence_parts = people.setdefault(name, [])
            if evidence not in evidence_parts:
                evidence_parts.append(evidence)

    if not people:
        raise ValueError("现任领导接口未解析到有效人物")

    return [
        {
            "name": name,
            "duty": "；".join(part.split("：", 1)[0] for part in evidence_parts),
            "evidence": "；".join(part.split("：", 1)[0] for part in evidence_parts),
            "detail_url": "",
        }
        for name, evidence_parts in people.items()
    ]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
