from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from crawler_core.fetcher import FetchResult
from crawler_core.settings import get_settings


ROLE_HINT_PATTERN = re.compile(
    r"(书记|副书记|主任|副主任|局长|副局长|厅长|副厅长|部长|副部长|院长|副院长|"
    r"主席|副主席|秘书长|副秘书长|馆长|所长|社长|庭长|副庭长|干部|专员|巡视员|"
    r"督察专员|总经理|董事长|负责人|委员|总工程师|总会计师|总经济师|现任职务|领导信息)"
)


@dataclass
class SnapshotQuality:
    """本地快照质量判断结果。"""

    ok: bool
    issue: str = ""


def safe_filename(value: str, max_length: int = 80) -> str:
    """生成 Windows 安全文件名片段。"""
    text = str(value or "").strip()
    for char in '\\/:*?"<>|':
        text = text.replace(char, "_")
    text = "_".join(text.split())
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:max_length] or "页面"


def build_snapshot_path(project_dir: Path, rule: dict[str, object]) -> Path:
    """按规则生成唯一快照路径，只保留一个版本。"""
    settings = get_settings()
    rule_id = str(rule.get("rule_id") or rule.get("规则ID") or "").strip().zfill(4)
    organization = safe_filename(str(rule.get("organization") or rule.get("机构") or "机构"))
    url = str(rule.get("url") or rule.get("领导信息链接") or "")
    domain = safe_filename(str(rule.get("domain") or rule.get("域名") or urlparse(url).netloc or "unknown"), 60)
    file_name = f"{rule_id}_{domain}_{organization}.html"
    return project_dir / settings.snapshot_dir_name / file_name


def find_existing_snapshot_path(project_dir: Path, rule: dict[str, object]) -> Path:
    """查找现有快照路径，兼容早期 RULE_ 前缀命名。"""
    snapshot_path = build_snapshot_path(project_dir, rule)
    if snapshot_path.is_file():
        return snapshot_path
    rule_prefixed_path = snapshot_path.with_name(f"RULE_{snapshot_path.name}")
    if rule_prefixed_path.is_file():
        return rule_prefixed_path
    return snapshot_path


def evaluate_snapshot_quality(html: str) -> SnapshotQuality:
    """判断快照是否可用于后续选择器和解析器探索。"""
    text = str(html or "")
    if len(text) < get_settings().suspicious_html_min_length:
        return SnapshotQuality(ok=False, issue=f"HTML 长度过短：{len(text)}")
    soup = BeautifulSoup(text, "html.parser")
    title_text = soup.title.get_text(" ", strip=True) if soup.title else ""
    body_text = soup.get_text(" ", strip=True)
    leading_text = (title_text + " " + body_text[:1200]).strip()
    for marker in ["访问异常", "验证码", "请开启 JavaScript", "请开启javascript", "浏览器版本过低", "系统维护", "页面不存在", "Not Found", "Forbidden"]:
        if marker in leading_text:
            return SnapshotQuality(ok=False, issue=f"疑似错误页：{marker}")
    if re.search(r"(^|\D)(403|404|500)(\D|$)", title_text):
        return SnapshotQuality(ok=False, issue=f"疑似错误页标题：{title_text}")
    if not ROLE_HINT_PATTERN.search(text):
        return SnapshotQuality(ok=False, issue="未发现常见领导/职务提示词")
    return SnapshotQuality(ok=True, issue="")


def save_snapshot(snapshot_path: Path, html: str, metadata: dict[str, object] | None = None) -> None:
    """覆盖保存单版本 HTML 快照。"""
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(normalize_snapshot_html(str(html or ""), metadata or {}), encoding="utf-8", errors="ignore")


def normalize_snapshot_html(html: str, metadata: dict[str, object]) -> str:
    """规范化快照 HTML，确保本地打开时按 UTF-8 解码。"""
    text = str(html or "")
    text = re.sub(r"<meta\s+[^>]*charset\s*=\s*['\"]?[^'\"\s>/]+['\"]?[^>]*>", "", text, flags=re.IGNORECASE)
    meta_charset = '<meta charset="utf-8">'
    final_url = str(metadata.get("snapshot_final_url") or metadata.get("snapshot_url") or "").strip()
    base_tag = f'<base href="{final_url}">' if final_url else ""
    preview_style = """
<style id="snapshot-preview-fix">
/* Snapshot preview fix: local tab switching while preserving original DOM selectors. */
.snapshot-tab-section {
  display: none !important;
}
.snapshot-tab-section.snapshot-visible {
  display: block !important;
  visibility: visible !important;
  opacity: 1 !important;
  height: auto !important;
  max-height: none !important;
}
.snapshot-tab-button {
  cursor: pointer !important;
}
.snapshot-tab-button.snapshot-active {
  outline: 2px solid #1D4ED8 !important;
  outline-offset: 2px !important;
}
</style>""".strip()
    head_inserts = "\n".join(item for item in [meta_charset, base_tag, preview_style] if item)
    if "<head" in text.lower():
        text = re.sub(r"(<head[^>]*>)", r"\1\n" + head_inserts, text, count=1, flags=re.IGNORECASE)
    else:
        text = head_inserts + "\n" + text

    lines = ["<!--"]
    for key, value in metadata.items():
        safe_value = str(value or "").replace("--", "- -").replace("\r", " ").replace("\n", " ")
        lines.append(f"{key}: {safe_value}")
    lines.append("-->")
    preview_script = """
<script id="snapshot-preview-tab-switcher">
(function () {
  function sectionKey(node) {
    var dataKey = node.getAttribute("data-showlist");
    if (dataKey) return String(dataKey);
    var match = (node.id || "").match(/^con-one-(\\d+)$/);
    return match ? match[1] : "";
  }

  function tabKey(node) {
    var dataKey = node.getAttribute("data-colname");
    if (dataKey) return String(dataKey);
    var idMatch = (node.id || "").match(/^one(\\d+)$/);
    if (idMatch) return idMatch[1];
    var text = (node.textContent || "").replace(/\\s+/g, "");
    if (text.indexOf("领导") >= 0) return "2";
    if (text.indexOf("内设") >= 0) return "3";
    if (text.indexOf("机关") >= 0 || text.indexOf("简介") >= 0 || text.indexOf("职能") >= 0) return "1";
    return "";
  }

  function allSections() {
    return Array.prototype.slice.call(document.querySelectorAll("[data-showlist], #con-one-1, #con-one-2, #con-one-3"))
      .filter(function (node) { return sectionKey(node); });
  }

  function allTabs() {
    return Array.prototype.slice.call(document.querySelectorAll("[data-colname], #one1, #one2, #one3, .jgzn_title li, .jgzn_left li"))
      .filter(function (node) { return tabKey(node); });
  }

  function showTab(key) {
    allSections().forEach(function (node) {
      var visible = sectionKey(node) === key;
      node.classList.add("snapshot-tab-section");
      node.classList.toggle("snapshot-visible", visible);
      node.style.display = visible ? "block" : "none";
      node.style.visibility = visible ? "visible" : "hidden";
      node.style.opacity = visible ? "1" : "0";
    });
    allTabs().forEach(function (node) {
      node.classList.add("snapshot-tab-button");
      node.classList.toggle("snapshot-active", tabKey(node) === key);
    });
  }

  function boot() {
    var tabs = allTabs();
    tabs.forEach(function (node) {
      node.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        showTab(tabKey(node));
      }, true);
    });
    var keys = allSections().map(sectionKey);
    showTab(keys.indexOf("2") >= 0 ? "2" : (keys[0] || "1"));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
</script>""".strip()
    if "</body>" in text.lower():
        text = re.sub(r"</body\s*>", lambda _match: preview_script + "\n</body>", text, count=1, flags=re.IGNORECASE)
    else:
        text = text + "\n" + preview_script
    return "\n".join(lines) + "\n" + text


def load_snapshot(snapshot_path: Path) -> str:
    """读取本地 HTML 快照。"""
    return snapshot_path.read_text(encoding="utf-8", errors="replace")


def make_snapshot_fetch_result(rule: dict[str, object], project_dir: Path) -> FetchResult:
    """把本地快照包装成 FetchResult，供解析器复用。"""
    snapshot_path = find_existing_snapshot_path(project_dir, rule)
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"本地快照不存在：{snapshot_path}")
    html = load_snapshot(snapshot_path)
    quality = evaluate_snapshot_quality(html)
    warnings = [quality.issue] if quality.issue else []
    return FetchResult(
        html=html,
        final_url=str(rule.get("final_url") or rule.get("url") or ""),
        collector="snapshot",
        warnings=warnings,
        status_code=0,
        content_type="text/html; charset=utf-8",
    )
