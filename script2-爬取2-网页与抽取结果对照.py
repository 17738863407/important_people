from __future__ import annotations

from dataclasses import dataclass
import json
import re
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path

from crawler_core.exporter import OUTPUT_FIELDS
from crawler_core.paths import (
    find_chrome_executable,
    resolve_external_path,
    resolve_path_argument,
    timestamped_output_path,
)


V3_OUTPUT_FIELDS = tuple(OUTPUT_FIELDS)


@dataclass
class PersonRow:
    """单条人物抽取结果。"""

    source_file: str
    order: str
    organization: str
    url: str
    name: str
    duty: str
    evidence: str
    detail_url: str
    script_number: str
    crawler_script_path: str


@dataclass
class PageGroup:
    """一个输出文件对应的在线核验页面。"""

    source_file: str
    organization: str
    url: str
    crawler_script_path: str
    rows: list[PersonRow]


def write_log(log_path: Path, message: str) -> None:
    """同时输出到控制台并追加写入日志。"""
    print(message)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def first_nonempty(item: dict[str, str], *field_names: str) -> str:
    """按优先级返回首个非空字段，兼容新旧输出表头。"""
    for field_name in field_names:
        value = str(item.get(field_name, "") or "").strip()
        if value:
            return value
    return ""


def find_crawler_script_path(project_dir: Path, output_path: Path, script_number: str) -> Path | None:
    """按V3及其现行分类目录优先级查找脚本，避免命中无关历史副本。"""
    site_adapters_dir = project_dir / "site_adapters"
    search_roots = [
        site_adapters_dir / "17待检测",
        site_adapters_dir / "成功",
        site_adapters_dir / "大模型",
        site_adapters_dir / "失败",
        site_adapters_dir / "验证",
        site_adapters_dir / "异常",
        site_adapters_dir / "V3",
        site_adapters_dir / "脚本01：成功脚本",
        site_adapters_dir / "脚本02：失败脚本",
        site_adapters_dir / "脚本03：大模型脚本",
        site_adapters_dir / "脚本04：异常脚本",
    ]
    search_roots = [path for path in search_roots if path.is_dir()]
    if not search_roots:
        return None

    exact_name = output_path.with_suffix(".py").name
    for search_root in search_roots:
        exact_matches = sorted(path for path in search_root.rglob(exact_name) if path.is_file())
        if exact_matches:
            return exact_matches[0]

    normalized_number = str(script_number or "").strip()
    if not normalized_number:
        match = re.match(r"^(\d{4,6})_", output_path.name)
        normalized_number = match.group(1) if match else ""
    if normalized_number:
        for search_root in search_roots:
            number_matches = sorted(
                path for path in search_root.rglob(f"{normalized_number}_*.py") if path.is_file()
            )
            if number_matches:
                return number_matches[0]
    return None


def parse_tsv_line(headers: list[str], line: str) -> dict[str, str]:
    """把一行制表符文本转换为字段字典。"""
    cells = line.split("\t")
    return {
        header.strip(): cells[index].strip() if index < len(cells) else ""
        for index, header in enumerate(headers)
    }


def read_tsv_output(output_path: Path, project_dir: Path) -> list[PersonRow]:
    """读取单个V3十二列输出TXT，拒绝把日志或其他报告误当抽取结果。"""
    lines = output_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return []

    headers = [header.strip() for header in lines[0].split("\t")]
    missing_fields = [field for field in V3_OUTPUT_FIELDS if field not in headers]
    if missing_fields:
        raise ValueError(f"不是V3十二列结果，缺少字段：{'、'.join(missing_fields)}")
    raw_items = [parse_tsv_line(headers, line) for line in lines[1:] if line.strip()]
    if not raw_items:
        return []

    first_item = raw_items[0]
    script_number = first_nonempty(first_item, "脚本序号")
    crawler_script_path = find_crawler_script_path(project_dir, output_path, script_number)
    crawler_script_text = str(crawler_script_path) if crawler_script_path else ""

    rows: list[PersonRow] = []
    for item in raw_items:
        evidence = first_nonempty(item, "依据说明")
        rows.append(
            PersonRow(
                source_file=output_path.name,
                order=first_nonempty(item, "排序*"),
                organization=first_nonempty(item, "机构"),
                url=first_nonempty(item, "依据链接"),
                name=first_nonempty(item, "姓名*"),
                duty=first_nonempty(item, "职务*", "依据说明"),
                evidence=evidence,
                detail_url=first_nonempty(item, "详情页链接"),
                script_number=first_nonempty(item, "脚本序号") or script_number,
                crawler_script_path=crawler_script_text,
            )
        )
    return rows


def iter_output_files(output_dir: Path) -> list[Path]:
    """递归获取所有输出 TXT，并按相对路径排序。"""
    if not output_dir.is_dir():
        return []
    return sorted(path for path in output_dir.rglob("*.txt") if path.is_file())


def build_page_groups(rows: list[PersonRow]) -> list[PageGroup]:
    """按输出文件分组，形成扩展可匹配的网页数据。"""
    rows_by_file: dict[str, list[PersonRow]] = {}
    for row in rows:
        rows_by_file.setdefault(row.source_file, []).append(row)

    groups: list[PageGroup] = []
    for source_file, file_rows in rows_by_file.items():
        first = file_rows[0]
        page_url = next((row.url for row in file_rows if row.url), "")
        organization = next((row.organization for row in file_rows if row.organization), "")
        groups.append(
            PageGroup(
                source_file=source_file,
                organization=organization,
                url=page_url,
                crawler_script_path=first.crawler_script_path,
                rows=file_rows,
            )
        )
    return sorted(groups, key=lambda group: group.source_file)


def build_extension_data(groups: list[PageGroup], generated_at: str) -> dict[str, object]:
    """生成 Chrome 扩展读取的 JSON 数据。"""
    pages: list[dict[str, object]] = []
    for group in groups:
        pages.append(
            {
                "sourceFile": group.source_file,
                "organization": group.organization,
                "url": group.url,
                "crawlerScriptPath": group.crawler_script_path,
                "rows": [
                    {
                        "order": row.order,
                        "name": row.name,
                        "duty": row.duty,
                        "evidence": row.evidence,
                        "detailUrl": row.detail_url,
                        "scriptNumber": row.script_number,
                    }
                    for row in group.rows
                ],
            }
        )
    return {
        "schemaVersion": 2,
        "generatedAt": generated_at,
        "pageCount": len(pages),
        "rowCount": sum(len(group.rows) for group in groups),
        "pages": pages,
    }


def write_extension_data(data_path: Path, groups: list[PageGroup], generated_at: str) -> None:
    """写出扩展数据文件。"""
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data = build_extension_data(groups, generated_at)
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_summary(summary_path: Path, groups: list[PageGroup], generated_at: str) -> None:
    """写出便于人工查看的制表符摘要。"""
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"生成时间\t{generated_at}",
        f"页面数\t{len(groups)}",
        f"人物记录数\t{sum(len(group.rows) for group in groups)}",
        "",
        "源文件\t机构\t依据链接\t人物数\t爬虫脚本",
    ]
    lines.extend(
        "\t".join(
            [
                group.source_file,
                group.organization,
                group.url,
                str(len(group.rows)),
                group.crawler_script_path,
            ]
        )
        for group in groups
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_extension_files(extension_dir: Path) -> list[Path]:
    """检查扩展静态文件是否齐全。"""
    required_paths = [
        extension_dir / "manifest.json",
        extension_dir / "content.js",
        extension_dir / "popup.html",
        extension_dir / "popup.js",
    ]
    return [path for path in required_paths if not path.is_file()]


def open_urls_in_browser(
    urls: list[str],
    log_path: Path,
    browser_path: Path | None,
    browser_user_data_dir: Path | None,
) -> None:
    """使用指定 Chrome 或系统默认浏览器批量打开在线核验网页。"""
    unique_urls = list(dict.fromkeys(url for url in urls if url))
    if not unique_urls:
        write_log(log_path, "没有可打开的在线核验网址。")
        return

    opened_count = 0
    if browser_path and browser_path.is_file():
        for start_index in range(0, len(unique_urls), 20):
            batch_urls = unique_urls[start_index : start_index + 20]
            command = [str(browser_path)]
            if browser_user_data_dir and browser_user_data_dir.is_dir():
                command.append(f"--user-data-dir={browser_user_data_dir}")
            command.append("--new-tab")
            command.extend(batch_urls)
            try:
                subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                opened_count += len(batch_urls)
            except Exception as error:
                write_log(log_path, f"指定浏览器打开失败，改用系统默认浏览器：{error}")
                break

    for url in unique_urls[opened_count:]:
        try:
            if webbrowser.open(url, new=2):
                opened_count += 1
        except Exception as error:
            write_log(log_path, f"跳过无法打开的网址：{url}，原因：{error}")
    write_log(log_path, f"已打开在线核验网页：{opened_count}/{len(unique_urls)} 个标签页")


def main(
    project_dir: str | Path,
    output_dir: str | Path | None,
    extension_dir: Path | None,
    summary_path: str | Path,
    log_path: str | Path,
    auto_open_source_pages: bool,
    browser_path: Path | None,
    browser_user_data_dir: Path | None,
    output_dir_environment: str = "IMPORTANT_PERSON_COMPARE_OUTPUT_DIR",
    extension_dir_environment: str = "IMPORTANT_PERSON_COMPARE_EXTENSION_DIR",
) -> Path:
    """读取在线抽取结果，为 Chrome 扩展生成最新对照数据。"""
    project_dir = resolve_path_argument(project_dir, anchor=__file__, must_exist=True)
    if output_dir is None:
        output_dir = resolve_external_path(output_dir_environment)
    else:
        output_dir = resolve_path_argument(output_dir, anchor=__file__, must_exist=True)
    extension_dir = extension_dir or resolve_external_path(extension_dir_environment)
    summary_path = resolve_path_argument(summary_path, anchor=__file__)
    log_path = resolve_path_argument(log_path, anchor=__file__)
    browser_path = browser_path or find_chrome_executable()
    started_at = datetime.now()
    run_timestamp = started_at.strftime("%Y%m%d_%H%M%S")
    summary_path = timestamped_output_path(summary_path, run_timestamp)
    log_path = timestamped_output_path(log_path, run_timestamp)
    generated_at = started_at.strftime("%Y-%m-%d %H:%M:%S")
    write_log(log_path, "=" * 72)
    write_log(log_path, f"开始更新 Chrome 扩展对照数据：{generated_at}")
    write_log(log_path, f"输出目录：{output_dir}")

    missing_extension_files = validate_extension_files(extension_dir)
    if missing_extension_files:
        missing_text = "、".join(str(path) for path in missing_extension_files)
        raise FileNotFoundError(f"Chrome 扩展文件不完整：{missing_text}")

    output_files = iter_output_files(output_dir)
    rows: list[PersonRow] = []
    skipped_file_count = 0
    try:
        from tqdm import tqdm
    except Exception:
        tqdm = None

    iterator = tqdm(output_files, desc="读取在线抽取结果") if tqdm else output_files
    for output_path in iterator:
        try:
            rows.extend(read_tsv_output(output_path, project_dir))
        except Exception as error:
            write_log(log_path, f"跳过文件：{output_path}，原因：{error}")
            skipped_file_count += 1

    groups = build_page_groups(rows)
    data_path = extension_dir / "data" / "extraction-results.json"
    write_extension_data(data_path, groups, generated_at)
    write_summary(summary_path, groups, generated_at)

    missing_url_count = sum(1 for group in groups if not group.url)
    incomplete_row_count = sum(1 for row in rows if not row.name or not row.duty)
    write_log(log_path, f"扩展数据：{data_path}")
    write_log(log_path, f"核验摘要：{summary_path}")
    write_log(log_path, f"页面数：{len(groups)}")
    write_log(log_path, f"人物记录数：{len(rows)}")
    write_log(log_path, f"跳过的非V3结果或异常文件：{skipped_file_count}")
    write_log(log_path, f"缺少依据链接的页面：{missing_url_count}")
    write_log(log_path, f"姓名或职务不完整的记录：{incomplete_row_count}")

    if auto_open_source_pages:
        open_urls_in_browser(
            urls=[group.url for group in groups],
            log_path=log_path,
            browser_path=browser_path,
            browser_user_data_dir=browser_user_data_dir,
        )

    write_log(log_path, f"更新完成：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return data_path


if __name__ == "__main__":
    project_dir_value = r"important_people"
    output_dir_value = r"important_people/outputs/x"
    extension_dir_value = None
    output_dir_environment_value = "IMPORTANT_PERSON_COMPARE_OUTPUT_DIR"
    extension_dir_environment_value = "IMPORTANT_PERSON_COMPARE_EXTENSION_DIR"
    summary_path_value = r"important_people/workspace/reports/Chrome扩展在线核验摘要.txt"
    log_path_value = r"important_people/workspace/log/网页与抽取结果对照.log"
    auto_open_source_pages_value = True
    browser_path_value = None
    # 普通网页对照直接复用新版 Chrome 的现有默认会话，不启用远程调试。
    browser_user_data_dir_value = None
    main(
        project_dir=project_dir_value,
        output_dir=output_dir_value,
        extension_dir=extension_dir_value,
        output_dir_environment=output_dir_environment_value,
        extension_dir_environment=extension_dir_environment_value,
        summary_path=summary_path_value,
        log_path=log_path_value,
        auto_open_source_pages=auto_open_source_pages_value,
        browser_path=browser_path_value,
        browser_user_data_dir=browser_user_data_dir_value,
    )
