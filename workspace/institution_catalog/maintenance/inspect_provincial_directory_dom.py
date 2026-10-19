"""检查省级政府机构目录页分类标题周边的DOM结构。"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from tqdm import tqdm

from crawler_core.paths import resolve_project_path
from workspace.institution_catalog.maintenance.extract_provincial_government_institution_candidates import (
    category_from_text,
    normalize_text,
)


def configure_logging(log_path: Path) -> logging.Logger:
    """配置控制台与UTF-8文件日志。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("provincial_directory_dom_inspector")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def describe_tag(node: Tag) -> str:
    """输出标签、ID、类名、短文本和链接数量。"""
    classes = ".".join(node.get("class", []))
    identity = f"#{node.get('id')}" if node.get("id") else ""
    text = normalize_text(node.get_text(" ", strip=True))[:80]
    return f"{node.name}{identity}.{classes} a={len(node.find_all('a', href=True))} text={text}"


def inspect_html(path: Path) -> list[str]:
    """定位最深层分类标题并记录四层祖先结构。"""
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    output = [f"### {path.name}"]
    seen: set[str] = set()
    for node in soup.find_all(True):
        category = category_from_text(node.get_text(" ", strip=True))
        if not category:
            continue
        child_has_category = any(category_from_text(child.get_text(" ", strip=True)) for child in node.find_all(True))
        if child_has_category:
            continue
        key = f"{category}|{node.name}|{node.get('id')}|{node.get('class')}"
        if key in seen:
            continue
        seen.add(key)
        output.append(f"CATEGORY {category}: {describe_tag(node)}")
        parent = node.parent
        for level in range(1, 5):
            if not isinstance(parent, Tag):
                break
            output.append(f"  P{level} {describe_tag(parent)}")
            parent = parent.parent
    output.append("")
    return output


def main(snapshot_dir: Path, output_path: Path, log_path: Path) -> None:
    """递归检查全部HTML快照并生成结构诊断报告。"""
    logger = configure_logging(log_path)
    lines: list[str] = []
    paths = sorted(snapshot_dir.glob("*.html"))
    for path in tqdm(paths, desc="检查目录DOM", unit="页"):
        try:
            lines.extend(inspect_html(path))
        except Exception:
            logger.exception("检查失败：%s", path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("结构诊断完成：%d页，%s", len(paths), output_path)


if __name__ == "__main__":
    snapshot_dir = resolve_project_path(r"important_people/workspace/snapshots/机构目录/省级政府机构目录/html", anchor=__file__, must_exist=True)
    output_path = resolve_project_path(r"important_people/workspace/reports/机构目录/省级政府机构目录DOM结构诊断.txt", anchor=__file__)
    log_path = resolve_project_path(r"important_people/workspace/log/机构目录/省级政府机构目录DOM检查.log", anchor=__file__)
    main(snapshot_dir, output_path, log_path)
