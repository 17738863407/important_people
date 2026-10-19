"""机构数据工作台的 SQLite 持久化、修订和安全发布服务。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


def now_text() -> str:
    """返回便于界面显示和排序的本地时间文本。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_value(value: Any) -> str:
    """清理会破坏制表符文本结构的控制字符。"""
    return str(value if value is not None else "").replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def read_tsv(path: Path) -> tuple[list[str], list[list[str]]]:
    """读取 UTF-8 制表符文件并严格校验每行字段数。"""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError(f"文件为空：{path}")
    headers = [clean_value(value) for value in lines[0].split("\t")]
    if not headers or any(not header for header in headers):
        raise ValueError("表头包含空字段名称")
    if len(headers) != len(set(headers)):
        raise ValueError("表头包含重复字段名称")
    rows: list[list[str]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        values = [clean_value(value) for value in line.split("\t")]
        if len(values) != len(headers):
            raise ValueError(f"第{line_number}行字段数为{len(values)}，应为{len(headers)}")
        rows.append(values)
    return headers, rows


def file_hash(path: Path) -> str:
    """计算文件 SHA-256。"""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_text(value: Any) -> str:
    """以稳定、可读的形式保存 JSON。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class WorkbenchStore:
    """管理工作台数据、字段、修订历史、冲突和正式文件发布。"""

    def __init__(self, database_path: Path, source_path: Path, backup_dir: Path) -> None:
        self.database_path = database_path
        self.source_path = source_path
        self.backup_dir = backup_dir
        self.lock = threading.RLock()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        """建立启用 WAL、外键和字典行的数据库连接。"""
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def transaction(self):
        """在提交或回滚后可靠关闭数据库连接。"""
        connection = self.connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        """初始化数据库结构，并在首次运行时导入正式表。"""
        with self.lock, self.transaction() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fields (
                    field_id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    export_name TEXT NOT NULL UNIQUE,
                    position INTEGER NOT NULL,
                    data_type TEXT NOT NULL DEFAULT 'text',
                    is_link INTEGER NOT NULL DEFAULT 0,
                    required INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS records (
                    record_id TEXT PRIMARY KEY,
                    sort_order INTEGER NOT NULL,
                    base_data TEXT NOT NULL,
                    data TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    deleted INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    record_id TEXT,
                    field_id TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    details TEXT NOT NULL DEFAULT '',
                    published INTEGER NOT NULL DEFAULT 0,
                    undone INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS conflicts (
                    conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT,
                    field_id TEXT,
                    conflict_type TEXT NOT NULL,
                    old_base TEXT NOT NULL DEFAULT '',
                    new_base TEXT NOT NULL DEFAULT '',
                    manual_value TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_records_sort_order ON records(sort_order);
                CREATE INDEX IF NOT EXISTS idx_revisions_created_at ON revisions(revision_id DESC);
                """
            )
            field_count = connection.execute("SELECT COUNT(*) FROM fields").fetchone()[0]
            if field_count == 0:
                self.import_initial(connection)

    def known_field_id(self, header: str, position: int) -> str:
        """把当前标准中文字段映射为稳定内部 ID。"""
        known_ids = {
            "组织体系": "organization_system",
            "目录链接": "directory_url",
            "机构类型": "institution_type",
            "机构层级": "institution_level",
            "所属省*": "province",
            "所属市": "city",
            "机构名称": "institution_name",
            "机构别称": "institution_alias",
            "官网链接": "official_url",
            "领导链接": "leader_url",
            "脚本序号": "script_sequence",
            "备注": "note",
            "依据链接": "evidence_url",
            "主表匹配": "master_match",
        }
        return known_ids.get(header, f"field_{position + 1}_{uuid.uuid4().hex[:8]}")

    def import_initial(self, connection: sqlite3.Connection) -> None:
        """首次运行时把正式 TXT 导入数据库。"""
        headers, source_rows = read_tsv(self.source_path)
        field_ids: list[str] = []
        for position, header in enumerate(headers):
            field_id = self.known_field_id(header, position)
            field_ids.append(field_id)
            connection.execute(
                "INSERT INTO fields(field_id, source_name, export_name, position, data_type, is_link, required) VALUES(?, ?, ?, ?, ?, ?, ?)",
                (
                    field_id,
                    header,
                    header,
                    position,
                    "url" if "链接" in header else "text",
                    1 if "链接" in header else 0,
                    1 if header == "机构名称" else 0,
                ),
            )

        timestamp = now_text()
        for sort_order, values in enumerate(source_rows):
            data = dict(zip(field_ids, values, strict=True))
            connection.execute(
                "INSERT INTO records(record_id, sort_order, base_data, data, origin, deleted, updated_at) VALUES(?, ?, ?, ?, 'source', 0, ?)",
                (uuid.uuid4().hex, sort_order, json_text(data), json_text(data), timestamp),
            )
        source_digest = file_hash(self.source_path)
        self.set_meta(connection, "source_hash", source_digest)
        self.set_meta(connection, "published_hash", source_digest)
        self.set_meta(connection, "initialized_at", timestamp)
        self.set_meta(connection, "schema_version", "1")

    def set_meta(self, connection: sqlite3.Connection, key: str, value: str) -> None:
        """写入一个元数据值。"""
        connection.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def get_meta(self, connection: sqlite3.Connection, key: str, default: str = "") -> str:
        """读取一个元数据值。"""
        row = connection.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def add_revision(
        self,
        connection: sqlite3.Connection,
        action: str,
        record_id: str | None = None,
        field_id: str | None = None,
        old_value: Any = None,
        new_value: Any = None,
        details: str = "",
        batch_id: str | None = None,
    ) -> None:
        """追加一条可审计修订记录。"""
        connection.execute(
            """
            INSERT INTO revisions(batch_id, created_at, action, record_id, field_id, old_value, new_value, details)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id or uuid.uuid4().hex,
                now_text(),
                action,
                record_id,
                field_id,
                None if old_value is None else json_text(old_value),
                None if new_value is None else json_text(new_value),
                details,
            ),
        )

    def list_fields(self, connection: sqlite3.Connection) -> list[dict[str, Any]]:
        """返回按显示顺序排列的字段定义。"""
        rows = connection.execute("SELECT * FROM fields ORDER BY position").fetchall()
        return [dict(row) for row in rows]

    def state(self) -> dict[str, Any]:
        """返回网页初始化所需的完整本地状态。"""
        with self.lock, self.transaction() as connection:
            fields = self.list_fields(connection)
            rows = connection.execute("SELECT * FROM records ORDER BY sort_order, record_id").fetchall()
            records = [
                {
                    "record_id": row["record_id"],
                    "sort_order": row["sort_order"],
                    "data": json.loads(row["data"]),
                    "origin": row["origin"],
                    "deleted": bool(row["deleted"]),
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]
            pending_count = connection.execute(
                "SELECT COUNT(*) FROM revisions WHERE published = 0 AND undone = 0"
            ).fetchone()[0]
            conflict_count = connection.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0]
            current_hash = file_hash(self.source_path) if self.source_path.exists() else ""
            published_hash = self.get_meta(connection, "published_hash")
            return {
                "fields": fields,
                "records": records,
                "status": {
                    "pending_count": pending_count,
                    "conflict_count": conflict_count,
                    "external_change": current_hash != published_hash,
                    "source_hash": current_hash,
                    "published_hash": published_hash,
                    "source_modified_at": datetime.fromtimestamp(self.source_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                },
            }

    def require_record(self, connection: sqlite3.Connection, record_id: str) -> sqlite3.Row:
        """取得指定记录，不存在时抛出明确错误。"""
        row = connection.execute("SELECT * FROM records WHERE record_id = ?", (record_id,)).fetchone()
        if row is None:
            raise KeyError("记录不存在")
        return row

    def require_field(self, connection: sqlite3.Connection, field_id: str) -> sqlite3.Row:
        """取得指定字段，不存在时抛出明确错误。"""
        row = connection.execute("SELECT * FROM fields WHERE field_id = ?", (field_id,)).fetchone()
        if row is None:
            raise KeyError("字段不存在")
        return row

    def update_record(self, record_id: str, field_id: str, value: Any) -> dict[str, Any]:
        """修改一个单元格并记录修订。"""
        new_value = clean_value(value)
        with self.lock, self.transaction() as connection:
            self.require_field(connection, field_id)
            row = self.require_record(connection, record_id)
            data = json.loads(row["data"])
            old_value = data.get(field_id, "")
            if old_value == new_value:
                return {"changed": False}
            data[field_id] = new_value
            connection.execute(
                "UPDATE records SET data = ?, updated_at = ? WHERE record_id = ?",
                (json_text(data), now_text(), record_id),
            )
            self.add_revision(connection, "edit", record_id, field_id, old_value, new_value)
            return {"changed": True, "value": new_value}

    def bulk_update(self, record_ids: list[str], field_id: str, value: Any) -> dict[str, Any]:
        """批量填写选中记录的一个字段。"""
        new_value = clean_value(value)
        changed_count = 0
        batch_id = uuid.uuid4().hex
        with self.lock, self.transaction() as connection:
            self.require_field(connection, field_id)
            for record_id in record_ids:
                row = self.require_record(connection, record_id)
                data = json.loads(row["data"])
                old_value = data.get(field_id, "")
                if old_value == new_value:
                    continue
                data[field_id] = new_value
                connection.execute(
                    "UPDATE records SET data = ?, updated_at = ? WHERE record_id = ?",
                    (json_text(data), now_text(), record_id),
                )
                self.add_revision(
                    connection,
                    "edit",
                    record_id,
                    field_id,
                    old_value,
                    new_value,
                    details="批量修改",
                    batch_id=batch_id,
                )
                changed_count += 1
        return {"changed_count": changed_count}

    def create_record(self, values: dict[str, Any] | None = None, duplicate_from: str | None = None) -> dict[str, Any]:
        """新增空记录或复制现有记录。"""
        with self.lock, self.transaction() as connection:
            fields = self.list_fields(connection)
            data = {field["field_id"]: "" for field in fields}
            action = "create"
            if duplicate_from:
                source = self.require_record(connection, duplicate_from)
                data.update(json.loads(source["data"]))
                action = "duplicate"
            if values:
                for field_id, value in values.items():
                    if any(field["field_id"] == field_id for field in fields):
                        data[field_id] = clean_value(value)
            max_order = connection.execute("SELECT COALESCE(MAX(sort_order), -1) FROM records").fetchone()[0]
            record_id = uuid.uuid4().hex
            connection.execute(
                "INSERT INTO records(record_id, sort_order, base_data, data, origin, deleted, updated_at) VALUES(?, ?, '{}', ?, 'manual', 0, ?)",
                (record_id, max_order + 1, json_text(data), now_text()),
            )
            self.add_revision(connection, action, record_id, new_value=data)
            return {"record_id": record_id, "sort_order": max_order + 1, "data": data, "origin": "manual", "deleted": False}

    def set_deleted(self, record_id: str, deleted: bool) -> dict[str, Any]:
        """软删除或恢复一条记录。"""
        with self.lock, self.transaction() as connection:
            row = self.require_record(connection, record_id)
            old_deleted = bool(row["deleted"])
            if old_deleted == deleted:
                return {"changed": False}
            connection.execute(
                "UPDATE records SET deleted = ?, updated_at = ? WHERE record_id = ?",
                (1 if deleted else 0, now_text(), record_id),
            )
            self.add_revision(connection, "delete" if deleted else "restore", record_id, old_value=old_deleted, new_value=deleted)
            return {"changed": True, "deleted": deleted}

    def rename_field(self, field_id: str, export_name: Any) -> dict[str, Any]:
        """修改网页和 TXT 使用的真实字段名称。"""
        new_name = clean_value(export_name)
        if not new_name:
            raise ValueError("字段名称不能为空")
        with self.lock, self.transaction() as connection:
            field = self.require_field(connection, field_id)
            old_name = field["export_name"]
            if old_name == new_name:
                return {"changed": False}
            duplicate = connection.execute(
                "SELECT 1 FROM fields WHERE export_name = ? AND field_id <> ?",
                (new_name, field_id),
            ).fetchone()
            if duplicate:
                raise ValueError("字段名称不能重复")
            connection.execute("UPDATE fields SET export_name = ? WHERE field_id = ?", (new_name, field_id))
            self.add_revision(connection, "rename_field", field_id=field_id, old_value=old_name, new_value=new_name)
            return {"changed": True, "export_name": new_name}

    def history(self, limit: int = 200) -> list[dict[str, Any]]:
        """返回最近修订记录。"""
        safe_limit = max(1, min(int(limit), 1000))
        with self.lock, self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM revisions ORDER BY revision_id DESC LIMIT ?", (safe_limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    def undo(self) -> dict[str, Any]:
        """撤销最近一条尚未撤销的用户修订。"""
        with self.lock, self.transaction() as connection:
            revision = connection.execute(
                """
                SELECT * FROM revisions
                WHERE undone = 0 AND action IN ('edit', 'create', 'duplicate', 'delete', 'restore', 'rename_field')
                ORDER BY revision_id DESC LIMIT 1
                """
            ).fetchone()
            if revision is None:
                return {"changed": False}
            action = revision["action"]
            if action == "edit":
                row = self.require_record(connection, revision["record_id"])
                data = json.loads(row["data"])
                data[revision["field_id"]] = json.loads(revision["old_value"])
                connection.execute(
                    "UPDATE records SET data = ?, updated_at = ? WHERE record_id = ?",
                    (json_text(data), now_text(), revision["record_id"]),
                )
            elif action in {"create", "duplicate"}:
                connection.execute("UPDATE records SET deleted = 1 WHERE record_id = ?", (revision["record_id"],))
            elif action == "delete":
                connection.execute("UPDATE records SET deleted = 0 WHERE record_id = ?", (revision["record_id"],))
            elif action == "restore":
                connection.execute("UPDATE records SET deleted = 1 WHERE record_id = ?", (revision["record_id"],))
            elif action == "rename_field":
                connection.execute(
                    "UPDATE fields SET export_name = ? WHERE field_id = ?",
                    (json.loads(revision["old_value"]), revision["field_id"]),
                )
            connection.execute("UPDATE revisions SET undone = 1 WHERE revision_id = ?", (revision["revision_id"],))
            self.add_revision(connection, "undo", revision["record_id"], revision["field_id"], details=f"撤销修订{revision['revision_id']}")
            return {"changed": True, "revision_id": revision["revision_id"]}

    def validate_for_publish(
        self,
        fields: list[dict[str, Any]],
        records: list[sqlite3.Row],
    ) -> None:
        """发布前校验字段、必填值和标准值域。"""
        export_names = [field["export_name"] for field in fields]
        if any(not name for name in export_names) or len(export_names) != len(set(export_names)):
            raise ValueError("字段名称为空或重复")
        field_ids = {field["field_id"] for field in fields}
        for row_number, row in enumerate(records, start=2):
            data = json.loads(row["data"])
            if "institution_name" in field_ids and not clean_value(data.get("institution_name", "")):
                raise ValueError(f"第{row_number}行机构名称为空")
            sequence = clean_value(data.get("script_sequence", ""))
            if "script_sequence" in field_ids and sequence and (
                len(sequence) != 4 or not sequence.isdigit()
            ):
                raise ValueError(f"第{row_number}行脚本序号必须为空或四位数字")

    def publish(self) -> dict[str, Any]:
        """把草稿安全发布到正式 TXT，并生成可恢复备份。"""
        with self.lock, self.transaction() as connection:
            current_hash = file_hash(self.source_path)
            published_hash = self.get_meta(connection, "published_hash")
            if current_hash != published_hash:
                raise RuntimeError("正式文件已被外部修改，请先执行重新同步")

            fields = self.list_fields(connection)
            records = connection.execute(
                "SELECT * FROM records WHERE deleted = 0 ORDER BY sort_order, record_id"
            ).fetchall()
            self.validate_for_publish(fields, records)

            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = self.backup_dir / f"机构全量表-网页发布前-{timestamp}.txt"
            shutil.copy2(self.source_path, backup_path)
            temporary_path = self.source_path.with_name(f"{self.source_path.name}.web.tmp")
            if temporary_path.exists():
                raise FileExistsError(f"存在未处理的网页发布临时文件：{temporary_path}")

            lines = ["\t".join(field["export_name"] for field in fields)]
            for row in records:
                data = json.loads(row["data"])
                lines.append("\t".join(clean_value(data.get(field["field_id"], "")) for field in fields))
            temporary_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8", newline="")
            verify_headers, verify_rows = read_tsv(temporary_path)
            if verify_headers != [field["export_name"] for field in fields] or len(verify_rows) != len(records):
                raise ValueError("发布临时文件复核失败")
            os.replace(temporary_path, self.source_path)

            new_hash = file_hash(self.source_path)
            self.set_meta(connection, "source_hash", new_hash)
            self.set_meta(connection, "published_hash", new_hash)
            self.set_meta(connection, "last_published_at", now_text())
            connection.execute("UPDATE revisions SET published = 1 WHERE undone = 0")
            self.add_revision(connection, "publish", details=f"发布{len(records)}条记录；备份={backup_path.name}")
            connection.execute("UPDATE revisions SET published = 1 WHERE action = 'publish'")
            return {"row_count": len(records), "backup_path": str(backup_path), "source_hash": new_hash}

    def row_signature(self, data: dict[str, str], field_ids: list[str]) -> str:
        """生成稳定的完整行签名。"""
        return hashlib.sha256(json_text([data.get(field_id, "") for field_id in field_ids]).encode("utf-8")).hexdigest()

    def identity_key(self, data: dict[str, str]) -> tuple[str, str, str]:
        """生成用于外部重建后匹配记录的保守组合键。"""
        return (
            data.get("organization_system", ""),
            data.get("institution_name", ""),
            data.get("institution_type", ""),
        )

    def reconcile(self) -> dict[str, Any]:
        """导入外部重建结果，并重新应用可定位的人工修订。"""
        headers, external_rows = read_tsv(self.source_path)
        with self.lock, self.transaction() as connection:
            fields = self.list_fields(connection)
            fields_by_source = {field["source_name"]: field for field in fields}
            fields_by_export = {field["export_name"]: field for field in fields}
            mapped_fields: list[dict[str, Any]] = []
            for position, header in enumerate(headers):
                field = fields_by_source.get(header) or fields_by_export.get(header)
                if field is None:
                    field_id = self.known_field_id(header, position)
                    connection.execute(
                        "INSERT INTO fields(field_id, source_name, export_name, position, data_type, is_link, required) VALUES(?, ?, ?, ?, ?, ?, 0)",
                        (field_id, header, header, position, "url" if "链接" in header else "text", 1 if "链接" in header else 0),
                    )
                    field = dict(connection.execute("SELECT * FROM fields WHERE field_id = ?", (field_id,)).fetchone())
                else:
                    connection.execute(
                        "UPDATE fields SET source_name = ?, export_name = ?, position = ?, data_type = ?, is_link = ? WHERE field_id = ?",
                        (
                            header,
                            header,
                            position,
                            "url" if "链接" in header else "text",
                            1 if "链接" in header else 0,
                            field["field_id"],
                        ),
                    )
                    field = dict(
                        connection.execute(
                            "SELECT * FROM fields WHERE field_id = ?", (field["field_id"],)
                        ).fetchone()
                    )
                mapped_fields.append(dict(field))

            field_ids = [field["field_id"] for field in mapped_fields]
            old_rows = connection.execute("SELECT * FROM records ORDER BY sort_order").fetchall()
            source_rows = [row for row in old_rows if row["origin"] != "manual"]
            manual_rows = [row for row in old_rows if row["origin"] == "manual"]

            exact_index: dict[str, list[sqlite3.Row]] = {}
            identity_index: dict[tuple[str, str, str], list[sqlite3.Row]] = {}
            for row in source_rows:
                base_data = json.loads(row["base_data"])
                exact_index.setdefault(self.row_signature(base_data, field_ids), []).append(row)
                identity_index.setdefault(self.identity_key(base_data), []).append(row)

            used_ids: set[str] = set()
            replacement_rows: list[tuple[str, int, str, str, str, int, str]] = []
            conflicts: list[tuple[str, str | None, str, str, str, str, str]] = []
            matched_count = 0
            for sort_order, values in enumerate(external_rows):
                new_base = {field["field_id"]: value for field, value in zip(mapped_fields, values, strict=True)}
                candidates = exact_index.get(self.row_signature(new_base, field_ids), [])
                if len(candidates) != 1:
                    candidates = identity_index.get(self.identity_key(new_base), [])
                matched = candidates[0] if len(candidates) == 1 and candidates[0]["record_id"] not in used_ids else None
                if matched is None:
                    record_id = uuid.uuid4().hex
                    current_data = new_base.copy()
                    deleted = 0
                    origin = "source"
                else:
                    record_id = matched["record_id"]
                    used_ids.add(record_id)
                    old_base = json.loads(matched["base_data"])
                    old_current = json.loads(matched["data"])
                    overrides = {
                        field_id: old_current.get(field_id, "")
                        for field_id in field_ids
                        if old_current.get(field_id, "") != old_base.get(field_id, "")
                    }
                    current_data = new_base.copy()
                    for field_id, manual_value in overrides.items():
                        if old_base.get(field_id, "") != new_base.get(field_id, "") and manual_value != new_base.get(field_id, ""):
                            conflicts.append(
                                (
                                    record_id,
                                    field_id,
                                    "field_changed_both",
                                    old_base.get(field_id, ""),
                                    new_base.get(field_id, ""),
                                    manual_value,
                                    now_text(),
                                )
                            )
                        current_data[field_id] = manual_value
                    deleted = matched["deleted"]
                    origin = "source"
                    matched_count += 1
                replacement_rows.append(
                    (record_id, sort_order, json_text(new_base), json_text(current_data), origin, deleted, now_text())
                )

            next_order = len(replacement_rows)
            for row in source_rows:
                if row["record_id"] in used_ids:
                    continue
                base_data = json.loads(row["base_data"])
                current_data = json.loads(row["data"])
                has_override = current_data != base_data or bool(row["deleted"])
                if has_override:
                    conflicts.append((row["record_id"], None, "record_missing", json_text(base_data), "", json_text(current_data), now_text()))
                    replacement_rows.append(
                        (row["record_id"], next_order, row["base_data"], row["data"], "orphan", row["deleted"], now_text())
                    )
                    next_order += 1

            for row in manual_rows:
                replacement_rows.append(
                    (row["record_id"], next_order, row["base_data"], row["data"], "manual", row["deleted"], now_text())
                )
                next_order += 1

            connection.execute("DELETE FROM records")
            connection.executemany(
                "INSERT INTO records(record_id, sort_order, base_data, data, origin, deleted, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                replacement_rows,
            )
            retained_field_ids = {field["field_id"] for field in mapped_fields}
            obsolete_field_ids = [
                field["field_id"] for field in fields if field["field_id"] not in retained_field_ids
            ]
            connection.executemany(
                "DELETE FROM fields WHERE field_id = ?",
                [(field_id,) for field_id in obsolete_field_ids],
            )
            connection.execute("DELETE FROM conflicts")
            connection.executemany(
                "INSERT INTO conflicts(record_id, field_id, conflict_type, old_base, new_base, manual_value, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                conflicts,
            )
            current_hash = file_hash(self.source_path)
            self.set_meta(connection, "source_hash", current_hash)
            self.set_meta(connection, "published_hash", current_hash)
            self.set_meta(connection, "last_reconciled_at", now_text())
            self.add_revision(
                connection,
                "reconcile",
                details=f"外部记录{len(external_rows)}条；匹配{matched_count}条；冲突{len(conflicts)}条",
            )
            return {
                "external_count": len(external_rows),
                "matched_count": matched_count,
                "conflict_count": len(conflicts),
                "manual_count": len(manual_rows),
            }
