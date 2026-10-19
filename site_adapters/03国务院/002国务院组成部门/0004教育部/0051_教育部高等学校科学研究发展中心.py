from __future__ import annotations

import base64
import hashlib
import json
import random
import re
import string
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0051",
    "page_type": "职务分组名单页",
    "structure_group": "签名接口现任领导分组正文",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http_api",
    "parser": "CutechSignedApiLeadersParser_v2",
    "leader_region_selector": ".textarea-box",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "SSR入口的正文容器为空，必须从当前前端签名接口动态定位标题为现任领导的文章；分组证据须完整重复给组内每人",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _make_headers(referer: str, body: dict | None = None) -> dict[str, str]:
    """按网站当前公开前端协议生成一次性签名请求头。"""
    app_id = "48b890d93ccb4a04bdfce37b86c0c97f"
    public_client_token = base64.b64decode("NmFtejNncnRpOXN4").decode("ascii")
    body_text = json.dumps(body, ensure_ascii=False, separators=(",", ":")) if body else ""
    nonce = "".join(random.choice(string.digits + string.ascii_letters) for _ in range(8))
    timestamp = str(int(time.time() * 1000))
    sign_source = "&".join(
        [
            f"appId={app_id}",
            f"appSecret={public_client_token}",
            f"nonce={nonce}",
            f"timestamp={timestamp}",
            "version=1.0",
            f"params={body_text}" if body else "",
        ]
    )
    return {
        "appId": app_id,
        "nonce": nonce,
        "timestamp": timestamp,
        "sign": hashlib.md5(sign_source.encode("utf-8")).hexdigest(),
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.cutech.edu.cn",
        "Referer": referer,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145.0 Safari/537.36",
    }


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """从签名接口动态查找现任领导文章并解析职务分组名单。"""
    api_base = "https://www.cutech.edu.cn/cms-api/service-cms"
    list_body = {"categoryId": 24, "currentPage": 1, "pageSize": 10}
    list_headers = _make_headers(base_url, list_body)
    list_headers["Content-Type"] = "application/json"
    list_response = requests.post(
        f"{api_base}/api/v1/open/queryCategoryArticlesPage",
        headers=list_headers,
        data=json.dumps(list_body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        timeout=30,
    )
    list_response.raise_for_status()
    articles = list_response.json().get("data", {}).get("records", [])
    article_id = next((item.get("id") for item in articles if item.get("title") == "现任领导"), None)
    if not article_id:
        raise RuntimeError("签名接口未找到标题为现任领导的文章")

    detail_response = requests.get(
        f"{api_base}/api/v1/open/queryArticleDetail/{article_id}",
        params={"categoryId": 24},
        headers=_make_headers(base_url),
        timeout=30,
    )
    detail_response.raise_for_status()
    content = str(detail_response.json().get("data", {}).get("content") or "")
    lines = [
        re.sub(r"\s+", " ", line.replace("\xa0", " ").replace("\u3000", " ")).strip()
        for line in BeautifulSoup(content, "html.parser").get_text("\n", strip=True).splitlines()
        if line.strip()
    ]

    records: list[dict] = []
    seen_names: set[str] = set()
    for line in lines:
        matched = re.fullmatch(r"(.+?)[：:]\s*(.+)", line)
        if not matched:
            continue
        duty = matched.group(1).strip()
        names_text = matched.group(2).strip()
        for value in re.split(r"[、，,]\s*", names_text):
            name = re.sub(r"\s+", "", value)
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names:
                continue
            seen_names.add(name)
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "parser": PAGE_RULE["parser"],
                    "selector_summary": "签名API categoryId=24；动态定位标题=现任领导；按正文分组行及行内名单顺序",
                }
            )
    if not records:
        raise RuntimeError("现任领导接口正文未解析到职务分组名单")
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
