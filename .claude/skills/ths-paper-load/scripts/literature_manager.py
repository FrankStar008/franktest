#!/usr/bin/env python3
"""
参考文献管理程序 — literature_manager.py

启动一个本地 HTTP 服务器，在浏览器中提供参考文献列表.xml 的查看和编辑界面。
卡片式纵向布局，展示每篇文献的全量信息。

用法:
  python literature_manager.py --xml 参考文献列表.xml --port 8765
  python literature_manager.py  # 使用默认值
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ── HTML/JS 前端（卡片式纵向布局）────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>参考文献管理</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background: #f0f2f5; color: #1d1d1f; font-size: 14px; }

/* ── Header ── */
header { background: #fff; border-bottom: 1px solid #e0e0e0; padding: 14px 24px;
         display: flex; align-items: center; justify-content: space-between;
         position: sticky; top: 0; z-index: 20; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
header h1 { font-size: 17px; font-weight: 700; letter-spacing: -.3px; }
.stats { color: #888; font-size: 12px; }

/* ── Toolbar ── */
.toolbar { padding: 12px 24px; display: flex; gap: 8px; align-items: center; }
.btn { padding: 7px 14px; border-radius: 8px; border: none; cursor: pointer;
       font-size: 13px; font-weight: 500; transition: background .15s; }
.btn-primary { background: #0071e3; color: #fff; }
.btn-primary:hover { background: #0077ed; }
.btn-secondary { background: #e8e8ed; color: #1d1d1f; }
.btn-secondary:hover { background: #d8d8dd; }
.search-box { flex: 1; max-width: 360px; padding: 7px 12px;
              border: 1px solid #d2d2d7; border-radius: 8px; font-size: 13px; outline: none; }
.search-box:focus { border-color: #0071e3; }

/* ── Card grid — 2-3 columns ── */
.card-list { padding: 0 24px 32px;
             display: grid;
             grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
             gap: 14px; }

.card { background: #fff; border-radius: 14px; padding: 20px 22px;
        box-shadow: 0 1px 4px rgba(0,0,0,.07); transition: box-shadow .15s; }
.card:hover { box-shadow: 0 3px 12px rgba(0,0,0,.11); }

/* ── Card header row ── */
.card-header { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 12px; }
.card-title { flex: 1; font-size: 15px; font-weight: 600; line-height: 1.45; color: #1d1d1f; }
.card-badges { display: flex; gap: 6px; align-items: center; flex-shrink: 0; }

/* ── Badges ── */
.tag { display: inline-block; padding: 2px 9px; border-radius: 12px;
       font-size: 11px; font-weight: 600; }
.tag-article { background: #e3f0ff; color: #0055cc; }
.tag-website { background: #e8f5e9; color: #2e7d32; }
.tag-book    { background: #fff3e0; color: #e65100; }

/* ── Toggle (referred) ── */
.toggle { width: 38px; height: 22px; border-radius: 11px; border: none; cursor: pointer;
          position: relative; transition: background .2s; flex-shrink: 0; }
.toggle.on  { background: #34c759; }
.toggle.off { background: #c7c7cc; }
.toggle::after { content: ""; position: absolute; top: 3px; width: 16px; height: 16px;
                 border-radius: 50%; background: #fff; transition: left .2s; box-shadow: 0 1px 3px rgba(0,0,0,.2); }
.toggle.on::after  { left: 19px; }
.toggle.off::after { left: 3px; }
.toggle-label { font-size: 11px; color: #888; white-space: nowrap; }

/* ── Field rows ── */
.field-row { display: flex; gap: 8px; margin-bottom: 8px; align-items: flex-start; }
.field-label { font-size: 11px; font-weight: 600; color: #888; text-transform: uppercase;
               letter-spacing: .4px; min-width: 56px; padding-top: 1px; flex-shrink: 0; }
.field-value { font-size: 13px; color: #333; line-height: 1.55; flex: 1; }
.field-value.mono { font-family: "SF Mono", Menlo, monospace; font-size: 12px;
                    background: #f5f5f7; padding: 6px 10px; border-radius: 6px;
                    white-space: pre-wrap; word-break: break-all; }
.field-value.muted { color: #aaa; font-style: italic; }

/* ── Cite field — read-only by default, editable on demand ── */
.cite-wrap { flex: 1; }
.cite-display { font-family: "SF Mono", Menlo, monospace; font-size: 12px;
                background: #f5f5f7; padding: 7px 10px; border-radius: 7px;
                line-height: 1.5; white-space: pre-wrap; word-break: break-all;
                color: #333; min-height: 36px; }
.cite-display.empty { color: #aaa; font-style: italic; font-family: inherit; }
.cite-textarea { display: none; width: 100%; padding: 7px 10px; border: 1px solid #0071e3;
                 border-radius: 7px; font-size: 12px; font-family: "SF Mono", Menlo, monospace;
                 resize: vertical; min-height: 52px; line-height: 1.5; outline: none; }
.cite-actions { display: flex; align-items: center; gap: 8px; margin-top: 5px; }
.edit-btn { padding: 3px 10px; background: transparent; color: #0071e3; border: 1px solid #0071e3;
            border-radius: 6px; cursor: pointer; font-size: 11px; }
.edit-btn:hover { background: #e8f0fe; }
.save-btn { display: none; padding: 4px 12px; background: #0071e3; color: #fff; border: none;
            border-radius: 6px; cursor: pointer; font-size: 12px; }
.save-btn:hover { background: #0077ed; }
.cancel-btn { display: none; padding: 4px 10px; background: transparent; color: #888;
              border: 1px solid #d2d2d7; border-radius: 6px; cursor: pointer; font-size: 12px; }
.cancel-btn:hover { background: #f5f5f7; }
.saved-msg { color: #34c759; font-size: 12px; display: none; }

/* ── Links ── */
.link { color: #0071e3; text-decoration: none; font-size: 12px; }
.link:hover { text-decoration: underline; }

/* ── Divider ── */
.card-divider { border: none; border-top: 1px solid #f0f0f0; margin: 12px 0; }

/* ── Empty state ── */
.empty-state { text-align: center; padding: 64px 24px; color: #aaa; }
.empty-state h3 { font-size: 16px; margin-bottom: 8px; color: #888; }

/* ── Modal ── */
.modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 100; }
.modal-overlay.show { display: flex; align-items: center; justify-content: center; }
.modal { background: #fff; border-radius: 16px; padding: 28px; width: 500px; max-width: 95vw; }
.modal h2 { font-size: 17px; font-weight: 600; margin-bottom: 20px; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; font-size: 13px; font-weight: 500; margin-bottom: 6px; color: #444; }
.form-group input, .form-group select, .form-group textarea {
  width: 100%; padding: 9px 12px; border: 1px solid #d2d2d7; border-radius: 8px;
  font-size: 13px; outline: none; }
.form-group input:focus, .form-group select:focus, .form-group textarea:focus { border-color: #0071e3; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 20px; }
</style>
</head>
<body>

<header>
  <h1>📚 参考文献管理</h1>
  <span class="stats" id="stats">加载中…</span>
</header>

<div class="toolbar">
  <button class="btn btn-primary" onclick="openNewModal()">＋ 新建记录</button>
  <input class="search-box" type="text" placeholder="搜索标题、摘要、引用…" oninput="filterCards(this.value)" />
  <button class="btn btn-secondary" onclick="loadData()">↻ 刷新</button>
</div>

<div class="card-list" id="card-list"></div>
<div class="empty-state" id="empty-state" style="display:none">
  <h3>暂无文献记录</h3>
  <p>点击「新建记录」手动添加，或运行 nyl-thesis-literature-find skill 自动检索。</p>
</div>

<!-- New record modal -->
<div class="modal-overlay" id="new-modal">
  <div class="modal">
    <h2>新建文献记录</h2>
    <div class="form-group">
      <label>标题 *</label>
      <input type="text" id="new-title" placeholder="论文/网页/图书标题" />
    </div>
    <div class="form-group">
      <label>类型 *</label>
      <select id="new-type">
        <option value="article">article（学术文章）</option>
        <option value="website">website（网页）</option>
        <option value="book">book（图书）</option>
      </select>
    </div>
    <div class="form-group" id="url-group" style="display:none">
      <label>地址 (URL)</label>
      <input type="text" id="new-url" placeholder="https://…" />
    </div>
    <div class="form-group">
      <label>GBT-7714 引用（可选）</label>
      <textarea id="new-cite" rows="3" placeholder="[N] 作者. 标题[J]. 期刊, 年份."></textarea>
    </div>
    <p style="font-size:12px;color:#aaa;margin-top:4px">
      摘要和关联由 nyl-thesis-literature-arrangement skill 自动补充。
    </p>
    <div class="modal-actions">
      <button class="btn btn-secondary" onclick="closeNewModal()">取消</button>
      <button class="btn btn-primary" onclick="submitNew()">创建</button>
    </div>
  </div>
</div>

<script>
let allData = [];

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function handleOpen(e, el) {
  e.preventDefault();
  const url = el.href;
  const res = await fetch(url);
  const data = await res.json();
  if (!data.ok) {
    el.style.color = '#c00';
    el.title = '文件不存在，请重新下载';
    el.textContent = '⚠️ ' + el.textContent.replace(/^[⚠️📄]\s*/, '');
  }
}

function titleOf(i) { return allData[i] ? allData[i].title : ''; }

async function loadData() {
  const res = await fetch('/api/list');
  allData = await res.json();
  renderCards(allData);
  const referred = allData.filter(r => r.referred === 'true' || r.referred === true).length;
  document.getElementById('stats').textContent =
    `共 ${allData.length} 条 · ${referred} 条引用中`;
}

function startEditCite(i) {
  document.getElementById(`cite-display-${i}`).style.display = 'none';
  document.getElementById(`cite-${i}`).style.display = 'block';
  document.getElementById(`edit-btn-${i}`).style.display = 'none';
  document.getElementById(`save-btn-${i}`).style.display = 'inline-block';
  document.getElementById(`cancel-btn-${i}`).style.display = 'inline-block';
  document.getElementById(`cite-${i}`).focus();
}

function cancelEditCite(i) {
  // Restore original value
  document.getElementById(`cite-${i}`).value = allData[i].cite || '';
  document.getElementById(`cite-display-${i}`).style.display = '';
  document.getElementById(`cite-${i}`).style.display = 'none';
  document.getElementById(`edit-btn-${i}`).style.display = 'inline-block';
  document.getElementById(`save-btn-${i}`).style.display = 'none';
  document.getElementById(`cancel-btn-${i}`).style.display = 'none';
}

function renderCards(data) {
  const list = document.getElementById('card-list');
  const empty = document.getElementById('empty-state');
  if (!data.length) { list.innerHTML = ''; empty.style.display = ''; return; }
  empty.style.display = 'none';

  list.innerHTML = data.map((r, i) => {
    const referred = r.referred === 'true' || r.referred === true;
    const typeTag = `<span class="tag tag-${r.type||'article'}">${esc(r.type||'article')}</span>`;
    const doiLink = r.doi
      ? `<a class="link" href="https://doi.org/${esc(r.doi)}" target="_blank">🔗 ${esc(r.doi)}</a>`
      : '<span class="field-value muted">—</span>';
    const pathLink = r.path
      ? `<a class="link" href="/open?path=${encodeURIComponent(r.path)}" target="_blank"
            onclick="handleOpen(event, this)">📄 ${esc(r.path)}</a>`
      : '<span class="field-value muted">未下载</span>';

    return `
<div class="card" id="card-${i}">
  <div class="card-header">
    <div class="card-title">${esc(r.title)}</div>
    <div class="card-badges">
      ${typeTag}
      <div style="display:flex;flex-direction:column;align-items:center;gap:2px">
        <button class="toggle ${referred?'on':'off'}" id="toggle-${i}"
          title="${referred?'引用中（点击取消）':'未引用（点击启用）'}"
          onclick="toggleReferred(${i})"></button>
        <span class="toggle-label">${referred?'引用中':'未引用'}</span>
      </div>
    </div>
  </div>

  ${r.abstract ? `
  <div class="field-row">
    <span class="field-label">摘要</span>
    <span class="field-value">${esc(r.abstract)}</span>
  </div>` : ''}

  ${r.related ? `
  <div class="field-row">
    <span class="field-label">关联</span>
    <span class="field-value">${esc(r.related)}</span>
  </div>` : ''}

  ${r.recommanded ? `
  <div class="field-row">
    <span class="field-label">推荐</span>
    <span class="field-value">${esc(r.recommanded)}</span>
  </div>` : ''}

  <hr class="card-divider">

  <div class="field-row">
    <span class="field-label">引用格式</span>
    <div class="cite-wrap">
      <div class="cite-display${r.cite ? '' : ' empty'}" id="cite-display-${i}">${r.cite ? esc(r.cite) : '暂无引用格式'}</div>
      <textarea class="cite-textarea" id="cite-${i}">${esc(r.cite||'')}</textarea>
      <div class="cite-actions">
        <button class="edit-btn" id="edit-btn-${i}" onclick="startEditCite(${i})">编辑</button>
        <button class="save-btn" id="save-btn-${i}" onclick="saveCite(${i})">保存</button>
        <button class="cancel-btn" id="cancel-btn-${i}" onclick="cancelEditCite(${i})">取消</button>
        <span class="saved-msg" id="saved-${i}">✓ 已保存</span>
      </div>
    </div>
  </div>

  <div class="field-row">
    <span class="field-label">DOI</span>
    <span class="field-value">${doiLink}</span>
  </div>

  <div class="field-row">
    <span class="field-label">文件</span>
    <span class="field-value">${pathLink}</span>
  </div>
</div>`;
  }).join('');
}

async function toggleReferred(i) {
  const current = allData[i].referred === 'true' || allData[i].referred === true;
  const newVal = !current;
  const title = titleOf(i);
  const btn = document.getElementById(`toggle-${i}`);
  btn.className = `toggle ${newVal ? 'on' : 'off'}`;
  btn.title = newVal ? '引用中（点击取消）' : '未引用（点击启用）';
  btn.nextElementSibling.textContent = newVal ? '引用中' : '未引用';
  await fetch('/api/update', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({title, field: 'referred', value: String(newVal)})
  });
  allData[i].referred = String(newVal);
  const referred = allData.filter(r => r.referred === 'true' || r.referred === true).length;
  document.getElementById('stats').textContent =
    `共 ${allData.length} 条 · ${referred} 条引用中`;
}

async function saveCite(i) {
  const title = titleOf(i);
  const cite = document.getElementById(`cite-${i}`).value;
  await fetch('/api/update', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({title, field: 'cite', value: cite})
  });
  allData[i].cite = cite;
  const msg = document.getElementById(`saved-${i}`);
  msg.style.display = 'inline';
  setTimeout(() => msg.style.display = 'none', 2000);
}

function filterCards(q) {
  if (!q.trim()) { renderCards(allData); return; }
  const lq = q.toLowerCase();
  renderCards(allData.filter(r =>
    (r.title||'').toLowerCase().includes(lq) ||
    (r.abstract||'').toLowerCase().includes(lq) ||
    (r.cite||'').toLowerCase().includes(lq) ||
    (r.related||'').toLowerCase().includes(lq)
  ));
}

function openNewModal() {
  document.getElementById('new-modal').classList.add('show');
  document.getElementById('new-title').focus();
}
function closeNewModal() {
  document.getElementById('new-modal').classList.remove('show');
  ['new-title','new-cite','new-url'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('new-type').value = 'article';
  document.getElementById('url-group').style.display = 'none';
}
document.getElementById('new-type').addEventListener('change', function() {
  document.getElementById('url-group').style.display =
    (this.value === 'website' || this.value === 'book') ? '' : 'none';
});

async function submitNew() {
  const title = document.getElementById('new-title').value.trim();
  if (!title) { alert('请填写标题'); return; }
  const type = document.getElementById('new-type').value;
  const url  = document.getElementById('new-url').value.trim();
  const cite = document.getElementById('new-cite').value.trim();
  const res = await fetch('/api/create', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({title, type, path: url, cite})
  });
  const result = await res.json();
  if (result.ok) { closeNewModal(); loadData(); }
  else alert('创建失败：' + result.error);
}

loadData();
</script>
</body>
</html>
"""


# ── XML helpers ────────────────────────────────────────────────────────────────

def load_xml(xml_path: Path) -> ET.ElementTree:
    if not xml_path.exists():
        root = ET.Element("references")
        tree = ET.ElementTree(root)
        tree.write(str(xml_path), encoding="utf-8", xml_declaration=True)
    return ET.parse(str(xml_path))


def save_xml(tree: ET.ElementTree, xml_path: Path) -> None:
    ET.indent(tree, space="  ")
    tree.write(str(xml_path), encoding="utf-8", xml_declaration=True)


def xml_to_records(tree: ET.ElementTree) -> list:
    records = []
    for lit in tree.getroot().findall("literature"):
        r = {}
        for field in ["title", "type", "path", "abstract", "related",
                      "recommanded", "cite", "doi", "referred"]:
            el = lit.find(field)
            r[field] = el.text or "" if el is not None else ""
        records.append(r)
    return records


def update_field(tree: ET.ElementTree, title: str, field: str, value: str) -> bool:
    for lit in tree.getroot().findall("literature"):
        t = lit.find("title")
        if t is not None and t.text == title:
            el = lit.find(field)
            if el is None:
                el = ET.SubElement(lit, field)
            el.text = value
            return True
    return False


def create_record(tree: ET.ElementTree, title: str, rtype: str,
                  path: str = "", cite: str = "") -> bool:
    for lit in tree.getroot().findall("literature"):
        t = lit.find("title")
        if t is not None and t.text == title:
            return False
    lit = ET.SubElement(tree.getroot(), "literature")
    for k, v in {"title": title, "type": rtype, "path": path,
                 "abstract": "", "related": "", "recommanded": "",
                 "cite": cite, "doi": "", "referred": "true"}.items():
        el = ET.SubElement(lit, k)
        el.text = v
    return True


# ── HTTP handler ───────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    xml_path: Path = Path("参考文献列表.xml")

    def log_message(self, fmt, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            body = HTML_TEMPLATE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/list":
            tree = load_xml(self.xml_path)
            self.send_json(xml_to_records(tree))
        elif path.startswith("/open"):
            qs = parse_qs(parsed.query)
            fp = qs.get("path", [""])[0]
            if fp:
                # Resolve relative paths against the XML file's directory
                p = Path(fp)
                if not p.is_absolute():
                    p = self.xml_path.parent / p
                if p.exists():
                    subprocess.Popen(["open", str(p)])
                    self.send_json({"ok": True})
                    return
            self.send_json({"ok": False, "error": "file not found"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        path = urlparse(self.path).path
        if path == "/api/update":
            tree = load_xml(self.xml_path)
            ok = update_field(tree, body["title"], body["field"], body["value"])
            if ok:
                save_xml(tree, self.xml_path)
            self.send_json({"ok": ok})
        elif path == "/api/create":
            tree = load_xml(self.xml_path)
            ok = create_record(tree, body["title"], body.get("type", "article"),
                               body.get("path", ""), body.get("cite", ""))
            if ok:
                save_xml(tree, self.xml_path)
                self.send_json({"ok": True})
            else:
                self.send_json({"ok": False, "error": "标题已存在"}, 409)
        else:
            self.send_response(404)
            self.end_headers()


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="参考文献管理程序")
    parser.add_argument("--xml", default="参考文献列表.xml", help="XML 文件路径")
    parser.add_argument("--port", type=int, default=8765, help="HTTP 端口")
    parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    Handler.xml_path = Path(args.xml).resolve()  # always absolute
    load_xml(Handler.xml_path)

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}"
    print(f"参考文献管理程序已启动: {url}")
    print(f"XML 文件: {Handler.xml_path.resolve()}")
    print("按 Ctrl+C 停止")

    if not args.no_open:
        threading.Timer(0.5, lambda: subprocess.Popen(["open", url])).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
