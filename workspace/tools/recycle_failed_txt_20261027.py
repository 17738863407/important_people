from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import stat
import struct
import time
from datetime import datetime, timezone
from uuid import uuid4

from send2trash import send2trash
from crawler_core.paths import resolve_project_path, resolve_external_path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(path, boundary=None):
    # 对完整字面量路径及全部祖先检查，拒绝重解析点或越界目标。
    for item in (path, *path.parents):
        if item.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RuntimeError(f"拒绝重解析点：{item}")
    resolved = path.resolve(strict=True)
    if boundary is not None and (resolved == boundary or not resolved.is_relative_to(boundary)):
        raise RuntimeError(f"越出清理范围：{path}")
    return resolved


def classify(data):
    lines = data.decode("utf-8-sig").splitlines()
    expected = "姓名*\t职务*\t排序*\t职级*\t所属省*\t所属市\t依据链接\t依据说明\t维护人\t机构\t详情页链接\t脚本序号".split("\t")
    if not lines or lines[0].split("\t") != expected:
        raise ValueError("十二列表头异常")
    rows = [line.split("\t") for line in lines[1:] if line.strip()]
    if not rows or any(len(row) != 12 for row in rows):
        raise ValueError("空结果或列数异常，停止清理以待核对")
    failed = all(not row[0].strip() and row[7].strip().startswith("抽取失败") for row in rows)
    return failed


def read_receipt(path):
    raw = path.read_bytes()
    if len(raw) < 24:
        raise ValueError(f"回收站元数据过短：{path}")
    version, size, ticks = struct.unpack_from("<QQQ", raw)
    if version == 2:
        length = struct.unpack_from("<I", raw, 24)[0]
        if len(raw) < 28 + length * 2:
            raise ValueError("回收站路径长度异常")
        original = raw[28:28 + length * 2].decode("utf-16-le").rstrip("\0")
    elif version == 1:
        original = raw[24:].decode("utf-16-le").split("\0", 1)[0]
    else:
        raise ValueError(f"未知回收站元数据版本：{version}")
    deleted = ticks / 10_000_000 - 11_644_473_600
    stored = path.with_name("$R" + path.name[2:])
    return {"metadata": str(path), "stored": str(stored), "original": original,
            "size": size, "deleted_timestamp": deleted,
            "deleted_at": datetime.fromtimestamp(deleted, timezone.utc).isoformat()}


def verified_recycle(source, backup, recycle_bin):
    # 回收之前冻结原内容；返回成功必须同时具备新增元数据和可读的完整存储内容。
    content = source.read_bytes()
    if backup.read_bytes() != content:
        raise RuntimeError(f"备份不匹配：{source}")
    before = {p.name for p in recycle_bin.glob("$I*")}
    started = time.time()
    try:
        send2trash(str(source))
        receipt = None
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            additions = [p for p in recycle_bin.glob("$I*") if p.name not in before]
            matches = []
            for item in additions:
                record = read_receipt(item)
                if os.path.normcase(record["original"]) == os.path.normcase(str(source)):
                    matches.append(record)
            if len(matches) > 1:
                raise RuntimeError("出现多条同源新增回收记录")
            if matches:
                receipt = matches[0]
                if Path(receipt["stored"]).exists():
                    break
            time.sleep(0.1)
        if receipt is None or source.exists():
            raise RuntimeError(f"未验证源文件消失及新增回收记录：{source}")
        if not started - 2 <= receipt["deleted_timestamp"] <= time.time() + 2:
            raise RuntimeError("回收时间不在本次操作时间范围")
        stored = Path(receipt["stored"])
        if receipt["size"] != len(content) or stored.read_bytes() != content:
            raise RuntimeError("回收站存储内容与已校验备份不一致")
        receipt["sha256"] = digest(content)
        return receipt
    except Exception:
        # 任何不确定状态立即停止；原文件消失时从已验证备份恢复，不覆盖现存文件。
        if not source.exists():
            with source.open("xb") as stream:
                stream.write(backup.read_bytes())
            if source.read_bytes() != content:
                raise RuntimeError(f"恢复校验失败：{source}")
            logging.error("验证未通过，已从备份恢复并校验：%s", source)
        raise


def append_audit(path, record):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def main(target_logic, reports_logic, logs_logic, final_logic, expected_ids):
    target = resolve_project_path(target_logic, anchor=__file__, must_exist=True)
    safe_path(target)
    recycle_bin = resolve_external_path("IMPORTANT_PEOPLE_RECYCLE_BIN")
    if target.drive.casefold() != recycle_bin.drive.casefold():
        raise RuntimeError("目标与回收站不在同一磁盘")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    reports = resolve_project_path(reports_logic, anchor=__file__)
    reports.mkdir(parents=True, exist_ok=True)
    run_dir = reports / run_id
    run_dir.mkdir(exist_ok=False)
    backups = run_dir / "备份_禁止自动清理"
    backups.mkdir()
    logs = resolve_project_path(logs_logic, anchor=__file__)
    logs.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(logs / f"失败TXT清理_{run_id}.log", encoding="utf-8")])
    audit = run_dir / "回收审计.jsonl"
    try:
        snapshot = []
        files = sorted(target.rglob("*.txt"))
        for source in files:
            safe_path(source, target)
            data = source.read_bytes()
            snapshot.append({"path": str(source), "relative": str(source.relative_to(target)),
                             "sha256": digest(data), "mtime_ns": source.stat().st_mtime_ns,
                             "size": len(data), "failed": classify(data)})
        failed = [record for record in snapshot if record["failed"]]
        if len(snapshot) != 124 or {Path(r["path"]).name[:4] for r in failed} != set(expected_ids.split()):
            raise RuntimeError("文件数量或失败清单相较只读核验发生变化，停止")
        (run_dir / "初始清单.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        # 仅备份待回收的文件；其余文件保存指纹用于最终逐项复核。
        for record in failed:
            source = Path(record["path"])
            backup = backups / record["relative"]
            backup.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            if digest(data) != record["sha256"]:
                raise RuntimeError(f"备份前源文件发生变化：{source}")
            with backup.open("xb") as stream:
                stream.write(data)
            if backup.read_bytes() != data:
                raise RuntimeError(f"备份校验失败：{source}")
        manifest = ["原路径\t备份路径\tSHA256\t字节数"]
        manifest.extend(f'{r["path"]}\t{backups / r["relative"]}\t{r["sha256"]}\t{r["size"]}' for r in failed)
        (run_dir / "备份清单.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
        logging.info("已校验备份 %s 份，位置：%s", len(failed), backups)
        probe = run_dir / f"回收验证_{uuid4().hex}.txt"
        probe_content = f"本轮回收测试，UTF-8可恢复性验证：{uuid4()}\n".encode("utf-8")
        with probe.open("xb") as stream:
            stream.write(probe_content)
        probe_backup = run_dir / "回收验证内容备份.txt"
        with probe_backup.open("xb") as stream:
            stream.write(probe_content)
        safe_path(probe, run_dir)
        probe_receipt = verified_recycle(probe, probe_backup, recycle_bin)
        append_audit(audit, {"type": "probe", **probe_receipt})
        logging.info("本轮测试文件回收记录、路径、时间及存储内容全部验证通过")
        for index, record in enumerate(failed, 1):
            source = Path(record["path"])
            safe_path(source, target)
            data = source.read_bytes()
            if digest(data) != record["sha256"] or not classify(data):
                raise RuntimeError(f"回收前状态改变：{source}")
            receipt = verified_recycle(source, backups / record["relative"], recycle_bin)
            append_audit(audit, {"type": "failed_txt", **receipt})
            logging.info("[%s/%s] 已逐项验证回收：%s", index, len(failed), source.name)
        remaining = sorted(target.rglob("*.txt"))
        expected_remaining = {r["path"]: r for r in snapshot if not r["failed"]}
        if {str(p) for p in remaining} != set(expected_remaining):
            raise RuntimeError("剩余文件清单不符")
        for source in remaining:
            data = source.read_bytes()
            if digest(data) != expected_remaining[str(source)]["sha256"] or classify(data):
                raise RuntimeError(f"保留文件改变或仍有明确失败：{source}")
        # 最终再次读取每一项回收记录及内容，确保可恢复证据持续有效。
        audited = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
        for entry in audited:
            current = read_receipt(Path(entry["metadata"]))
            if current["original"] != entry["original"] or digest(Path(current["stored"]).read_bytes()) != entry["sha256"]:
                raise RuntimeError("最终回收证据复核失败")
        result = [f"检查目录：{target}", f"检查TXT：{len(snapshot)}份", f"明确失败且已验证移入回收站：{len(failed)}份", f"保留TXT：{len(remaining)}份", "判定标准：全部数据行姓名为空，且依据说明均以抽取失败开头。", "保留文件内容SHA256逐项核验未变化；未重跑采集、未修改规则主表或脚本。", f"已校验备份：{backups}", f"逐项回收审计（含原路径、时间、回收站存储路径及内容SHA256）：{audit}", "备份不纳入自动清理；本轮未执行永久删除。", "", "已回收文件："]
        result.extend(Path(r["path"]).name for r in failed)
        final = resolve_project_path(final_logic, anchor=__file__)
        with final.open("x", encoding="utf-8") as stream:
            stream.write("\n".join(result) + "\n")
        logging.info("完成：检查 %s，回收 %s，保留 %s。报告：%s", len(snapshot), len(failed), len(remaining), final)
    except Exception:
        logging.exception("已停止后续回收；保留全部备份及现场：%s", run_dir)
        raise


if __name__ == "__main__":
    target_logic = "important_people/outputs/二次"
    reports_logic = "important_people/workspace/reports/失败TXT清理_20261027"
    logs_logic = "important_people/workspace/log"
    final_logic = "important_people/失败TXT清理结果_20261027.txt"
    expected_ids = "0045 0241 0772 1003 1148 1212 1905 3481 3528 3602 3771 3779 3797 3886 3947 4017 4214 4287 4307 4383 4389 4417 4418 4428 4430 4490 4503 4506 4527 4562 4576 4578 4580"
    main(target_logic, reports_logic, logs_logic, final_logic, expected_ids)
