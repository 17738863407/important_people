from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1269",
    "page_type": "人物列表完整页",
    "structure_group": "DES加密中心领导接口",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "JtzyzgEncryptedLeaderApiParser_v2",
    "leader_region_selector": "LTPU_getLeaderAndDepartDuty result[depart=0].postlist",
    "name_selector": "postlist.leaders[].name",
    "duty_selector": "postlist.postname",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "api_endpoint": "https://www.jtzyzg.org.cn/LTPU/restservices/http/single/query",
    "api_method": "POST",
    "api_service": "LTPU_getLeaderAndDepartDuty",
    "risk_flag": "页面HTML为短展示壳且online会被验证码脚本文字拦截，使用raw_http进入解析；中心领导来自DES接口，须限定depart=0并按leaders.sort恢复顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def _fetch_leader_payload() -> dict:
    """调用网站前端同款DES接口，返回当前在线领导JSON。"""
    node_path = shutil.which("node")
    if not node_path:
        raise RuntimeError("未找到Node.js，无法调用站点DES加密接口")
    node_code = r'''
const vm = require("vm");
(async () => {
  const cryptoSource = await (await fetch(
    "https://www.jtzyzg.org.cn/LTPU/LEAP/home/weblib/CryptoJs/crypto-js.js"
  )).text();
  const sandbox = { module: { exports: {} }, exports: {} };
  vm.runInNewContext(cryptoSource, sandbox);
  const CryptoJS = sandbox.module.exports;
  const key = CryptoJS.enc.Utf8.parse("longrise211thsssdsaqqas");
  const encrypt = (value) => CryptoJS.DES.encrypt(value, key, {
    mode: CryptoJS.mode.ECB,
    padding: CryptoJS.pad.Pkcs7,
  }).toString();
  const response = await fetch(
    "https://www.jtzyzg.org.cn/LTPU/restservices/http/single/query",
    {
      method: "POST",
      headers: {
        "content-type": "application/json;charset=UTF-8",
        "referer": "https://www.jtzyzg.org.cn/LTPU/LEAP/home/html/centerInt.html",
      },
      body: JSON.stringify({
        service: encrypt("LTPU_getLeaderAndDepartDuty"),
        version: encrypt("1.0.0"),
        data: encrypt(JSON.stringify(null)),
      }),
    }
  );
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  console.log(await response.text());
})().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
});
'''
    completed = subprocess.run(
        [node_path, "-e", node_code],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("中心领导接口未返回JSON对象")
    return payload


def _sort_value(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 9999


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """限定中心领导分组，按接口人物sort抽取姓名与postname原字段。"""
    payload = _fetch_leader_payload()
    result = payload.get("result")
    groups = result.get("result") if isinstance(result, dict) else []
    center_group = next(
        (
            group
            for group in groups or []
            if isinstance(group, dict)
            and (
                _clean_text(str(group.get("depart", ""))) == "0"
                or _clean_text(str(group.get("departname", ""))) == "中心领导"
            )
        ),
        None,
    )
    if not isinstance(center_group, dict):
        raise RuntimeError("接口响应未找到中心领导分组")

    candidates: list[tuple[int, str, str]] = []
    for post in center_group.get("postlist") or []:
        if not isinstance(post, dict):
            continue
        evidence = _clean_text(str(post.get("postname", "")))
        for leader in post.get("leaders") or []:
            if not isinstance(leader, dict):
                continue
            name = re.sub(r"\s+", "", _clean_text(str(leader.get("name", ""))))
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) and evidence:
                candidates.append((_sort_value(leader.get("sort")), name, evidence))
    candidates.sort(key=lambda item: item[0])

    records: list[dict] = []
    seen_names: set[str] = set()
    for _, name, evidence in candidates:
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "DES接口；depart=0中心领导；leaders.sort；name；postname",
            }
        )
    if not records:
        raise RuntimeError("中心领导接口未解析到人物记录")
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
