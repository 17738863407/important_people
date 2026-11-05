from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
from uuid import uuid4

import send2trash

from crawler_core.paths import resolve_external_path, resolve_project_path
from workspace.tools.recycle_failed_txt_20261027 import (
    append_audit,
    digest,
    read_receipt,
    safe_path,
    verified_recycle,
)


def main(success_logic, failed_logic, manifest_logic, reports_logic, logs_logic, final_logic):
    success = resolve_project_path(success_logic, anchor=__file__, must_exist=True)
    failed = resolve_project_path(failed_logic, anchor=__file__, must_exist=True)
    manifest = resolve_project_path(manifest_logic, anchor=__file__, must_exist=True)
    reports = resolve_project_path(reports_logic, anchor=__file__, must_exist=True)
    logs = resolve_project_path(logs_logic, anchor=__file__, must_exist=True)
    recycle_bin = resolve_external_path("IMPORTANT_PEOPLE_RECYCLE_BIN", must_exist=False)
    safe_path(success)
    safe_path(failed)
    if failed.drive.casefold() != recycle_bin.drive.casefold():
        raise RuntimeError("回收站与目标不在同一磁盘")
    if send2trash.send2trash.__module__ != "send2trash.win.modern":
        raise RuntimeError("必须使用强制回收的现代Windows接口")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    run_dir = reports / ("同名TXT回收_" + stamp)
    run_dir.mkdir(exist_ok=False)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(
                            logs / ("同名TXT回收_" + stamp + ".log"), encoding="utf-8")])
    audit = run_dir / "回收审计.jsonl"
    try:
        success_files = list(success.glob("*.txt"))
        failed_files = list(failed.glob("*.txt"))
        success_names = {p.name.casefold() for p in success_files}
        # 重复判定仅使用完整文件名；内容指纹仅用于保护文件和校验备份。
        duplicate_files = [p for p in failed_files if p.name.casefold() in success_names]
        records = json.loads(manifest.read_text(encoding="utf-8-sig"))
        by_path = {str(Path(r["Original"])).casefold(): r for r in records}
        if {str(p).casefold() for p in duplicate_files} != set(by_path):
            raise RuntimeError("当前重复清单与已备份清单不一致，停止")
        snapshot = {}
        for path in success_files + failed_files:
            safe_path(path, success if path.parent == success else failed)
            snapshot[str(path)] = digest(path.read_bytes())
        for source in duplicate_files:
            record = by_path[str(source).casefold()]
            backup = Path(record["Backup"])
            safe_path(backup, manifest.parent)
            if source.read_bytes() != backup.read_bytes() or digest(backup.read_bytes()) != record["SHA256"].lower():
                raise RuntimeError(f"原文件或备份不符：{source}")
        (run_dir / "初始指纹.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        logging.info("已核验 %s 个同名文件及独立备份", len(duplicate_files))
        # 在本次实际账户与磁盘上先测试；失败时不会触碰用户原文件。
        probe = run_dir / ("回收验证_" + uuid4().hex + ".txt")
        probe_backup = run_dir / "回收验证内容备份.txt"
        content = ("本轮回收验证：" + uuid4().hex).encode("utf-8")
        with probe.open("xb") as stream:
            stream.write(content)
        with probe_backup.open("xb") as stream:
            stream.write(content)
        safe_path(probe, run_dir)
        receipt = verified_recycle(probe, probe_backup, recycle_bin)
        append_audit(audit, {"type": "probe", **receipt})
        logging.info("测试文件的回收记录、原路径、时间及存储内容均验证通过")
        for index, source in enumerate(duplicate_files, 1):
            safe_path(source, failed)
            record = by_path[str(source).casefold()]
            if digest(source.read_bytes()) != snapshot[str(source)]:
                raise RuntimeError(f"原文件变化：{source}")
            if not (success / source.name).is_file():
                raise RuntimeError(f"成功目录同名文件已不存在：{source.name}")
            receipt = verified_recycle(source, Path(record["Backup"]), recycle_bin)
            append_audit(audit, {"type": "duplicate_txt", **receipt})
            logging.info("[%s/%s] 已验证回收：%s", index, len(duplicate_files), source.name)
        removed = {str(p) for p in duplicate_files}
        remaining = list(success.glob("*.txt")) + list(failed.glob("*.txt"))
        if {str(p) for p in remaining} != set(snapshot) - removed:
            raise RuntimeError("保留文件清单不符")
        for path in remaining:
            if digest(path.read_bytes()) != snapshot[str(path)]:
                raise RuntimeError(f"保留文件内容改变：{path}")
        if {p.name.casefold() for p in success.glob("*.txt")} & {p.name.casefold() for p in failed.glob("*.txt")}:
            raise RuntimeError("仍有同名文件")
        entries = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
        for entry in entries:
            current = read_receipt(Path(entry["metadata"]))
            if current["original"] != entry["original"] or digest(Path(current["stored"]).read_bytes()) != entry["sha256"]:
                raise RuntimeError("最终回收证据校验失败")
        final = resolve_project_path(final_logic, anchor=__file__)
        result = ["判定标准：仅按TXT完整文件名。", f"保留二次成功TXT：{len(success_files)}",
                  f"失败目录同名TXT已逐项验证移入回收站：{len(duplicate_files)}",
                  f"失败目录剩余TXT：{len(failed_files) - len(duplicate_files)}", "两目录同名交集：0",
                  "保留文件指纹全部未变；独立备份保留，禁止自动清理。",
                  f"备份及原路径清单：{manifest}", f"回收审计：{audit}", "", "已回收文件名："]
        result.extend(p.name for p in duplicate_files)
        with final.open("x", encoding="utf-8") as stream:
            stream.write("\n".join(result) + "\n")
        logging.info("完成，报告：%s", final)
    except Exception:
        logging.exception("已停止后续回收，保留现场及备份：%s", run_dir)
        raise


if __name__ == "__main__":
    success_logic = "important_people/outputs/二次成功"
    failed_logic = "important_people/outputs/失败"
    manifest_logic = "important_people/workspace/reports/同名TXT去重_20261028_143827_fe79be65/重复及备份清单.json"
    reports_logic = "important_people/workspace/reports"
    logs_logic = "important_people/workspace/log"
    final_logic = "important_people/同名TXT回收完成结果_20261028.txt"
    main(success_logic, failed_logic, manifest_logic, reports_logic, logs_logic, final_logic)
