from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import logging
import py_compile
import sys
import time
from pathlib import Path


def project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到项目根目录")


def main(group: int, sequence: str, action: str, reason: str) -> None:
    root = project_root()
    sys.path.insert(0, str(root))
    from crawler_core.paths import resolve_project_path
    from crawler_core.business_sources import apply_business_source
    from crawler_core import runner
    base = resolve_project_path("important_people/workspace/reports/失败修复_20261026", anchor=__file__)
    log_dir = resolve_project_path("important_people/workspace/log", anchor=__file__)
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_dir / f"失败修复恢复{group}.log", encoding="utf-8")])
    assignment = json.loads((base / f"分配{group}.json").read_text(encoding="utf-8"))
    item = next(v for v in assignment["items"] if v["id"] == sequence)
    script = Path(item["scripts"][0])
    report_file = base / f"恢复验收{group}.json"
    existing = json.loads(report_file.read_text(encoding="utf-8")) if report_file.exists() else {"group": group, "items": []}
    previous = next((v for v in existing["items"] if v["id"] == sequence), {})
    record = dict(previous)
    record.update(id=sequence, file=item["file"], script=str(script), action=action)
    stage = base / f"恢复暂存{group}"
    stage.mkdir(exist_ok=True)
    started = time.monotonic()
    if action == "skip":
        record.update(status="跳过", reason=reason, accepted=False)
    elif action in {"accept", "review"}:
        if not record.get("extraction_succeeded"):
            raise RuntimeError("没有本次有效抽取，不能验收")
        output = Path(record["staged_output"])
        from shutil import copyfile
        target = root / "outputs" / output.name
        copyfile(output, target)
        if output.read_bytes() != target.read_bytes():
            raise RuntimeError("输出复制不一致")
        record.update(status="通过" if action == "accept" else "人工复核", reason=reason, accepted=action == "accept", output=str(target))
    else:
        code = script.read_text(encoding="utf-8-sig")
        record.setdefault("before_sha256", hashlib.sha256(script.read_bytes()).hexdigest())
        record["current_sha256"] = hashlib.sha256(script.read_bytes()).hexdigest()
        ast.parse(code, filename=str(script))
        py_compile.compile(str(script), doraise=True)
        record["syntax"] = "AST和py_compile通过"
        spec = importlib.util.spec_from_file_location(f"repair_{sequence}", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rule = dict(module.PAGE_RULE)
        # 本次显式HTTP运行，防止公共降级链启动未授权界面；不写回页面规则。
        rule.update(_fetch_mode_override=True, fetch_mode="requests")
        record["business"] = apply_business_source(rule)
        import requests
        original_send = requests.sessions.Session.send
        traces = []
        def capture_send(session, request, **kwargs):
            response = original_send(session, request, **kwargs)
            evidence = base / f"{sequence}_response_{len(traces)+1}.bin"
            evidence.write_bytes(response.content)
            traces.append({"url": response.url, "status": response.status_code, "path": str(evidence), "sha256": hashlib.sha256(response.content).hexdigest()})
            return response
        requests.sessions.Session.send = capture_send
        original_fetch = runner.fetch_html_for_rule
        def capture_fetch(*args, **kwargs):
            result, snapshot = original_fetch(*args, **kwargs)
            evidence_path = base / f"{sequence}_本次在线页面.html"
            evidence_path.write_text(result.html, encoding="utf-8")
            record["html"] = str(evidence_path)
            record["html_sha256"] = hashlib.sha256(result.html.encode("utf-8")).hexdigest()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(result.html, "html.parser")
            record["headings"] = [n.get_text(" ", strip=True) for n in soup.select("h1,h2,h3,[data-tag=header]")][:80]
            return result, snapshot
        runner.fetch_html_for_rule = capture_fetch
        context = {}
        try:
            output = runner.run_page_adapter(rule, vars(module), output_dir=stage, runtime_context=context, update_fetch_memory=False)
        finally:
            runner.fetch_html_for_rule = original_fetch
            requests.sessions.Session.send = original_send
            record["responses"] = traces
        lines = output.read_text(encoding="utf-8-sig").splitlines()
        cells = [l.split("\t") for l in lines[1:] if l]
        record.update(context)
        record.update(staged_output=str(output), status="待人工验收" if context.get("extraction_succeeded") else "抽取失败", accepted=False, rows=cells, header=lines[0], columns_valid=all(len(r)==12 for r in cells), elapsed_seconds=round(time.monotonic()-started,2))
    record["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    existing["items"] = [v for v in existing["items"] if v["id"] != sequence] + [record]
    report_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    progress = ["脚本序号\t状态\t说明"] + [f"{r['id']}\t{r['status']}\t{r.get('reason',r.get('error',''))}" for r in existing["items"]]
    (base / f"恢复进度{group}.txt").write_text("\n".join(progress)+"\n", encoding="utf-8")
    logging.info(json.dumps({k:record.get(k) for k in ("id","status","syntax","error","reason","elapsed_seconds","output")}, ensure_ascii=False))
    if action == "run":
        print(json.dumps(record.get("rows", []), ensure_ascii=False))


if __name__ == "__main__":
    group = int(sys.argv[1])
    sequence = sys.argv[2]
    action = sys.argv[3] if len(sys.argv)>3 else "run"
    reason = sys.argv[4] if len(sys.argv)>4 else ""
    main(group, sequence, action, reason)
