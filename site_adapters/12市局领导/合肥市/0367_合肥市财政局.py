from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0367",
    "page_type": "人物列表完整页",
    "structure_group": "hefei_public_info_leader_api",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "api_direct",
    "collector": "custom_api_http",
    "parser": "hefei_finance_public_info_api_v1",
    "leader_region_selector": "api:/mayor/site/label/8888",
    "name_selector": "json.data[*].title冒号后姓名",
    "duty_selector": "json.data[*].title冒号前原始职务",
    "detail_link_selector": "json.data[*].link",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "api_item_link",
        "detail_link_selector": "json.data[*].link",
        "max_detail_links": 50,
    },
    "risk_flag": "入口与接口均使用521 JavaScript cookie防护；仅接受解锁后HTTP 200且organId、organName和catId一致的数据",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "2026-08-08在线验证官方接口返回7条合肥市财政局机构领导记录",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "",
            "name_selector": "",
            "duty_selector": "",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": True,
            "endpoint_path": "/mayor/site/label/8888",
            "method": "GET",
            "labelName": "publicInfoList",
            "siteId": "6784341",
            "organId": "4381",
            "catIds": "7036024",
            "pageSize": "20",
            "pageIndex": "1",
            "data_path": "data",
            "name_field": "title冒号后",
            "duty_field": "title冒号前",
            "detail_url_field": "link",
        },
    },
}


def hash_text(value: str, algorithm: str) -> str:
    """按防护页声明的算法计算候选Cookie摘要。"""
    normalized_algorithm = str(algorithm or "sha256").lower()
    if normalized_algorithm == "md5":
        return hashlib.md5(value.encode("utf-8")).hexdigest()
    if normalized_algorithm == "sha1":
        return hashlib.sha1(value.encode("utf-8")).hexdigest()
    if normalized_algorithm == "sha256":
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    raise ValueError(f"不支持的校验哈希算法：{normalized_algorithm}")


def apply_cookie_string(session: requests.Session, cookie_text: str, domain: str) -> bool:
    """把JavaScript计算出的单个Cookie写入当前请求会话。"""
    if "=" not in cookie_text:
        return False
    name, remainder = cookie_text.strip().split("=", 1)
    value = remainder.split(";", 1)[0]
    if not name or not value:
        return False
    session.cookies.set(name, value, domain=domain, path="/")
    return True


def apply_simple_js_cookie(
    session: requests.Session,
    html: str,
    response_url: str,
    domain: str,
    node_executable: str,
) -> bool:
    """使用本机Node执行防护页中的确定性Cookie表达式。"""
    match = re.search(r"<script>(.*?)</script>", html, re.IGNORECASE | re.DOTALL)
    if not match or "document.cookie" not in match.group(1):
        return False
    parsed_url = urlsplit(response_url)
    search = f"?{parsed_url.query}" if parsed_url.query else ""
    javascript = "\n".join(
        [
            'const document = {cookie: ""};',
            f"const location = {{pathname: {json.dumps(parsed_url.path)}, search: {json.dumps(search)}, href: \"\"}};",
            match.group(1),
            "console.log(document.cookie);",
        ]
    )
    result = subprocess.run(
        [node_executable, "-e", javascript],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return result.returncode == 0 and apply_cookie_string(session, result.stdout.strip(), domain)


def apply_hash_js_cookie(session: requests.Session, html: str, domain: str) -> bool:
    """穷举防护页给出的两个字符并写入校验Cookie。"""
    match = re.search(r"go\((\{.*?\})\)\s*</script>", html, re.DOTALL)
    if not match:
        return False
    challenge = json.loads(match.group(1))
    boundaries = challenge.get("bts") or []
    characters = str(challenge.get("chars") or "")
    target_hash = str(challenge.get("ct") or "")
    if len(boundaries) != 2 or not characters or not target_hash:
        return False
    for suffix in [str(boundaries[1]), unquote(str(boundaries[1]))]:
        for first_character in characters:
            for second_character in characters:
                cookie_value = str(boundaries[0]) + first_character + second_character + suffix
                if hash_text(cookie_value, str(challenge.get("ha") or "sha256")) == target_hash:
                    cookie_name = str(challenge.get("tn") or "__jsl_clearance_s")
                    session.cookies.set(cookie_name, cookie_value, domain=domain, path="/")
                    return True
    return False


def request_with_js_clearance(
    session: requests.Session,
    url: str,
    headers: dict[str, str],
    params: dict[str, str],
    domain: str,
) -> requests.Response:
    """处理官方站点521防护并返回最终响应。"""
    node_executable = shutil.which("node")
    if not node_executable:
        raise RuntimeError("未找到Node.js，无法计算站点防护Cookie")
    last_response: requests.Response | None = None
    for _ in range(6):
        response = session.get(url, headers=headers, params=params, timeout=30)
        response.encoding = "utf-8"
        last_response = response
        if response.status_code != 521:
            return response
        if apply_simple_js_cookie(session, response.text, response.url, domain, node_executable):
            continue
        if apply_hash_js_cookie(session, response.text, domain):
            time.sleep(1.6)
            continue
        break
    if last_response is None:
        raise RuntimeError("接口请求未产生响应")
    return last_response


def build_api_params(page_rule: dict[str, object]) -> dict[str, str]:
    """从页面技术配置构造官方机构领导接口参数。"""
    api_config = dict(page_rule.get("locator", {}).get("api", {}))
    return {
        "labelName": str(api_config["labelName"]),
        "siteId": str(api_config["siteId"]),
        "organId": str(api_config["organId"]),
        "pageSize": str(api_config["pageSize"]),
        "pageIndex": str(api_config["pageIndex"]),
        "isDate": "true",
        "dateFormat": "yyyy-MM-dd",
        "length": "50",
        "type": "4",
        "action": "list",
        "result": "",
        "isJson": "true",
        "keyWords": "",
        "isRel": "true",
        "catIds": str(api_config["catIds"]),
    }


def fetch_leader_items(page_rule: dict[str, object]) -> list[dict[str, object]]:
    """在线读取并严格校验官方机构领导JSON数组。"""
    source_url = str(page_rule.get("url") or "")
    parsed_source = urlsplit(source_url)
    api_config = dict(page_rule.get("locator", {}).get("api", {}))
    api_url = f"{parsed_source.scheme}://{parsed_source.netloc}{api_config['endpoint_path']}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": source_url,
        "X-Requested-With": "XMLHttpRequest",
    }
    response = request_with_js_clearance(
        requests.Session(),
        api_url,
        headers,
        build_api_params(page_rule),
        parsed_source.netloc,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get(str(api_config.get("data_path") or "data"))
    if not isinstance(items, list):
        raise RuntimeError("官方接口返回中缺少data数组")
    expected_organ_id = int(str(api_config["organId"]))
    expected_cat_id = int(str(api_config["catIds"]))
    expected_organization = str(page_rule.get("organization") or "")
    valid_items = [
        item
        for item in items
        if isinstance(item, dict)
        and int(item.get("organId") or 0) == expected_organ_id
        and int(item.get("catId") or 0) == expected_cat_id
        and str(item.get("organName") or "") == expected_organization
    ]
    if len(valid_items) != len(items):
        raise RuntimeError("官方接口返回包含机构或栏目不一致的记录")
    return valid_items


def build_records(page_rule: dict[str, object], items: list[dict[str, object]]) -> list[object]:
    """按官方接口数组顺序构造人物记录。"""
    from crawler_core.models import PersonRecord

    rows: list[PersonRecord] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_api；endpoint=/mayor/site/label/8888；"
        "organId=4381；catId=7036024；fields=title/link"
    )
    for item in items:
        title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()
        duty, separator, name = title.partition("：")
        name = name.strip()
        duty = duty.strip()
        detail_url = str(item.get("link") or "").strip()
        if not separator or not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
            continue
        if not duty or not detail_url or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            PersonRecord(
                organization=str(page_rule.get("organization") or ""),
                url=str(page_rule.get("url") or ""),
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=str(page_rule.get("parser") or ""),
                selector_summary=selector_summary,
                script_sequence=str(page_rule.get("rule_id") or "").zfill(4),
            )
        )
    return rows


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """页面内置解析入口：在线取得官方API数组并构造人物记录。"""
    del html, final_url
    return build_records(page_rule, fetch_leader_items(page_rule))


def main() -> None:
    """运行合肥市财政局官方机构领导接口采集流程。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.business_sources import apply_business_source
    from crawler_core.exporter import export_records
    from crawler_core.runner import make_failure_record, safe_filename

    page_rule = apply_business_source(PAGE_RULE)
    try:
        rows = parse_page("", str(page_rule.get("url") or ""), page_rule)
        if not rows:
            rows = [make_failure_record(page_rule, "官方接口解析结果为空")]
    except Exception as error:
        rows = [make_failure_record(page_rule, str(error))]
    output_name = "_".join(
        [
            str(page_rule.get("rule_id") or "").zfill(4),
            safe_filename(str(page_rule.get("page_type") or "未知页面类型")),
            safe_filename(str(page_rule.get("load_mode") or "未知加载方式")),
            safe_filename(str(page_rule.get("organization") or "页面")),
        ]
    ) + ".txt"
    output_path = project_dir / "outputs" / output_name
    export_records(output_path, rows)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
