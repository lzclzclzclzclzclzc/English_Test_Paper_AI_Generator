"""One-off script: render data/kb/knowledge_tree_draft.json as a standalone
review-friendly HTML page. No build system, no CDN — the produced .html is
self-contained; double-click to open in any browser.

Usage:  python -m ingestion.viz_knowledge_tree
Output: data/kb/knowledge_tree_draft.html
"""
from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict


SRC = Path("data/kb/knowledge_tree_draft.json")
OUT = Path("data/kb/knowledge_tree_draft.html")
CHAPTERS_DIR = Path("data/chapters")

LEVEL1_LABEL = {
    "single_choice": "单项选择",
    "word_form": "词性转换",
    "sentence_rewriting": "改写句子",
}


def load_data() -> dict:
    tree = json.loads(SRC.read_text(encoding="utf-8"))

    # Count questions per (question_type, chapter_l1, chapter_l2) so we can
    # show题量 in the mapping panel.
    counts: dict[str, int] = defaultdict(int)
    for slug in ("shanghai_2021_yimo", "shanghai_2021_ermo"):
        path = CHAPTERS_DIR / f"{slug}.json"
        if not path.is_file():
            continue
        for q in json.loads(path.read_text(encoding="utf-8")):
            key = f"{q['question_type']} / {q['chapter_l1']} / {q['chapter_l2']}"
            counts[key] += 1

    # Reverse mapping: kp_id → [chapter_key, ...]
    reverse: dict[str, list[str]] = defaultdict(list)
    for chapter_key, kp_ids in tree["chapter_to_kp"].items():
        for kp_id in kp_ids:
            reverse[kp_id].append(chapter_key)

    return {
        "note": tree.get("_note", ""),
        "knowledge_points": tree["knowledge_points"],
        "chapter_to_kp": tree["chapter_to_kp"],
        "reverse": reverse,
        "counts": counts,
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>知识点树 · 审核视图</title>
<style>
  :root {
    --bg: #f7f8fa;
    --panel: #ffffff;
    --border: #e2e6ea;
    --text: #24292f;
    --muted: #6a737d;
    --accent: #0969da;
    --highlight-bg: #fff8c5;
    --highlight-border: #eac54f;
    --sc: #0969da;
    --wf: #1a7f37;
    --sr: #bf3989;
    --tag-bg: #eef1f4;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                 "Microsoft YaHei", sans-serif;
    background: var(--bg); color: var(--text);
    font-size: 14px; line-height: 1.5;
  }
  header {
    background: var(--panel); border-bottom: 1px solid var(--border);
    padding: 14px 20px; position: sticky; top: 0; z-index: 10;
  }
  header h1 { margin: 0; font-size: 18px; }
  header .note { color: var(--muted); font-size: 12px; margin-top: 4px; }
  .search-row {
    margin-top: 10px; display: flex; gap: 8px; align-items: center;
  }
  input[type=search] {
    flex: 1; padding: 6px 10px; border: 1px solid var(--border);
    border-radius: 6px; font-size: 13px;
  }
  button {
    padding: 6px 10px; border: 1px solid var(--border);
    background: white; border-radius: 6px; cursor: pointer; font-size: 12px;
  }
  button:hover { background: #f0f3f6; }

  main {
    display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
    padding: 16px 20px;
  }
  .panel {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 8px; overflow: hidden;
    max-height: calc(100vh - 140px); overflow-y: auto;
  }
  .panel-header {
    background: #fafbfc; border-bottom: 1px solid var(--border);
    padding: 8px 14px; font-weight: 600; font-size: 13px;
    position: sticky; top: 0; z-index: 5;
  }
  .panel-body { padding: 10px 14px; }

  /* KP list --------------------------------- */
  .tabs { display: flex; gap: 4px; margin: 8px 0; }
  .tab {
    padding: 4px 10px; border: 1px solid var(--border);
    border-radius: 4px; cursor: pointer; font-size: 12px; background: white;
  }
  .tab.active { background: var(--accent); color: white; border-color: var(--accent); }

  .kp-group h3 {
    margin: 12px 0 6px; font-size: 13px; color: var(--muted);
    border-bottom: 1px dashed var(--border); padding-bottom: 4px;
  }
  .kp-item {
    padding: 6px 10px; margin: 2px 0; border-radius: 4px; cursor: pointer;
    border: 1px solid transparent;
  }
  .kp-item:hover { background: #f0f3f6; }
  .kp-item.highlight { background: var(--highlight-bg); border-color: var(--highlight-border); }
  .kp-item.selected  { background: var(--highlight-bg); border-color: var(--highlight-border); }
  .kp-id { font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 11px; color: var(--muted); }
  .kp-name { font-weight: 500; }
  .kp-aliases { color: var(--muted); font-size: 11px; margin-top: 2px; }
  .badge { display: inline-block; padding: 1px 6px; border-radius: 10px;
           font-size: 10px; color: white; margin-right: 6px; font-weight: 600; }
  .badge-single_choice     { background: var(--sc); }
  .badge-word_form         { background: var(--wf); }
  .badge-sentence_rewriting{ background: var(--sr); }

  /* Mapping list --------------------------- */
  .chapter-group { margin-bottom: 16px; }
  .chapter-group h3 {
    margin: 8px 0 6px; font-size: 13px; color: var(--muted);
    border-bottom: 1px dashed var(--border); padding-bottom: 4px;
  }
  .map-row {
    display: grid; grid-template-columns: 1fr auto;
    padding: 6px 10px; margin: 2px 0; border-radius: 4px; cursor: pointer;
    border: 1px solid transparent; align-items: start; gap: 8px;
  }
  .map-row:hover { background: #f0f3f6; }
  .map-row.highlight { background: var(--highlight-bg); border-color: var(--highlight-border); }
  .map-row.selected  { background: var(--highlight-bg); border-color: var(--highlight-border); }
  .map-left .chapter-name { font-weight: 500; }
  .map-left .chapter-meta { font-size: 11px; color: var(--muted); margin-top: 2px; }
  .map-right { display: flex; gap: 4px; flex-wrap: wrap; justify-content: flex-end; }
  .kp-chip {
    padding: 2px 8px; background: var(--tag-bg); border-radius: 3px;
    font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 11px;
    cursor: pointer; border: 1px solid transparent;
  }
  .kp-chip:hover { border-color: var(--accent); }
  .kp-chip.multi { background: #fff1e5; }  /* one chapter → multiple KP */

  .count-pill {
    display: inline-block; background: #eef1f4; color: var(--muted);
    padding: 1px 6px; border-radius: 10px; font-size: 11px; margin-left: 4px;
  }
  .stats { color: var(--muted); font-size: 12px; margin-left: 8px; font-weight: normal; }
  .hidden { display: none !important; }
</style>
</head>
<body>

<header>
  <h1>知识点树 · 审核视图 <span class="stats" id="stats"></span></h1>
  <div class="note">__NOTE__</div>
  <div class="search-row">
    <input type="search" id="search" placeholder="搜索 KP id / 中文名 / 章节标题 ...">
    <button id="clear">清除高亮</button>
  </div>
</header>

<main>
  <section class="panel">
    <div class="panel-header">
      知识点（KP）
      <span class="stats" id="kp-count"></span>
      <span class="tabs" id="kp-tabs">
        <button class="tab active" data-level1="all">全部</button>
        <button class="tab" data-level1="single_choice">单选</button>
        <button class="tab" data-level1="word_form">词性转换</button>
        <button class="tab" data-level1="sentence_rewriting">改写句子</button>
      </span>
    </div>
    <div class="panel-body" id="kp-panel"></div>
  </section>

  <section class="panel">
    <div class="panel-header">
      章节 → KP 映射
      <span class="stats" id="map-count"></span>
    </div>
    <div class="panel-body" id="map-panel"></div>
  </section>
</main>

<script>
const DATA = __DATA_JSON__;
const KP_INDEX = Object.fromEntries(DATA.knowledge_points.map(k => [k.id, k]));

// ─── render KP list ──────────────────────────────────────────
function renderKPs(filter) {
  const container = document.getElementById('kp-panel');
  container.innerHTML = '';
  const groups = {single_choice: [], word_form: [], sentence_rewriting: []};
  for (const kp of DATA.knowledge_points) groups[kp.level1].push(kp);
  const labels = {single_choice: '单项选择', word_form: '词性转换', sentence_rewriting: '改写句子'};

  for (const [lvl, kps] of Object.entries(groups)) {
    if (filter !== 'all' && filter !== lvl) continue;
    const g = document.createElement('div');
    g.className = 'kp-group';
    g.innerHTML = `<h3>${labels[lvl]} (${kps.length})</h3>`;
    for (const kp of kps) {
      const chapters = DATA.reverse[kp.id] || [];
      const total = chapters.reduce((s, ck) => s + (DATA.counts[ck] || 0), 0);
      const item = document.createElement('div');
      item.className = 'kp-item';
      item.dataset.kpId = kp.id;
      item.dataset.searchable = [
        kp.id, kp.level2, ...(kp.aliases || [])
      ].join(' ').toLowerCase();
      item.innerHTML = `
        <div>
          <span class="badge badge-${kp.level1}">${labels[kp.level1]}</span>
          <span class="kp-name">${kp.level2}</span>
          <span class="count-pill">${chapters.length} 章 · ${total} 题</span>
        </div>
        <div class="kp-id">${kp.id}</div>
        ${(kp.aliases && kp.aliases.length) ? `<div class="kp-aliases">别名: ${kp.aliases.join(' · ')}</div>` : ''}
      `;
      item.onclick = () => selectKP(kp.id);
      g.appendChild(item);
    }
    container.appendChild(g);
  }
}

// ─── render Mapping list ─────────────────────────────────────
function renderMappings() {
  const container = document.getElementById('map-panel');
  container.innerHTML = '';
  // group by chapter_l1
  const groups = {};
  for (const [key, kpIds] of Object.entries(DATA.chapter_to_kp)) {
    const [qt, l1, l2] = key.split(' / ');
    const gkey = `${qt}::${l1}`;
    if (!groups[gkey]) groups[gkey] = {qt, l1, entries: []};
    groups[gkey].entries.push({key, qt, l1, l2, kpIds});
  }
  const labels = {single_choice: '单项选择', word_form: '词性转换', sentence_rewriting: '改写句子'};

  // sort groups: single_choice > word_form > sentence_rewriting
  const order = ['single_choice', 'word_form', 'sentence_rewriting'];
  const sortedGroups = Object.values(groups).sort((a, b) =>
    order.indexOf(a.qt) - order.indexOf(b.qt) || a.l1.localeCompare(b.l1));

  for (const g of sortedGroups) {
    const groupDiv = document.createElement('div');
    groupDiv.className = 'chapter-group';
    groupDiv.innerHTML = `<h3><span class="badge badge-${g.qt}">${labels[g.qt]}</span> ${g.l1} (${g.entries.length})</h3>`;
    // sort entries by l2 (natural order)
    g.entries.sort((a, b) => a.l2.localeCompare(b.l2, 'zh'));
    for (const e of g.entries) {
      const count = DATA.counts[e.key] || 0;
      const row = document.createElement('div');
      row.className = 'map-row';
      row.dataset.chapterKey = e.key;
      row.dataset.searchable = [e.qt, e.l1, e.l2, ...e.kpIds].join(' ').toLowerCase();
      const chips = e.kpIds.map(id => {
        const kp = KP_INDEX[id];
        const cls = e.kpIds.length > 1 ? 'kp-chip multi' : 'kp-chip';
        return `<span class="${cls}" data-kp-id="${id}" title="${kp ? kp.level2 : ''}">${id}</span>`;
      }).join('');
      row.innerHTML = `
        <div class="map-left">
          <div class="chapter-name">${e.l2}</div>
          <div class="chapter-meta">${count} 题</div>
        </div>
        <div class="map-right">${chips}</div>
      `;
      // click row → highlight target KPs
      row.onclick = (ev) => {
        // if user clicked a chip, respect that click's own handler
        if (ev.target.classList.contains('kp-chip')) return;
        selectChapter(e.key);
      };
      groupDiv.appendChild(row);
    }
    container.appendChild(groupDiv);
  }
  // wire chip clicks
  container.querySelectorAll('.kp-chip').forEach(chip => {
    chip.onclick = (ev) => {
      ev.stopPropagation();
      selectKP(chip.dataset.kpId);
    };
  });
}

// ─── selection & highlighting ────────────────────────────────
function clearHighlight() {
  document.querySelectorAll('.highlight, .selected').forEach(el =>
    el.classList.remove('highlight', 'selected'));
}
function selectKP(kpId) {
  clearHighlight();
  document.querySelectorAll(`.kp-item[data-kp-id="${kpId}"]`).forEach(el => {
    el.classList.add('selected');
    el.scrollIntoView({block: 'center', behavior: 'smooth'});
  });
  const chapters = DATA.reverse[kpId] || [];
  chapters.forEach(ck => {
    document.querySelectorAll(`.map-row[data-chapter-key="${CSS.escape(ck)}"]`).forEach(el =>
      el.classList.add('highlight'));
  });
  const first = document.querySelector('.map-row.highlight');
  if (first) first.scrollIntoView({block: 'center', behavior: 'smooth'});
}
function selectChapter(chapterKey) {
  clearHighlight();
  document.querySelectorAll(`.map-row[data-chapter-key="${CSS.escape(chapterKey)}"]`).forEach(el => {
    el.classList.add('selected');
    el.scrollIntoView({block: 'center', behavior: 'smooth'});
  });
  const kpIds = DATA.chapter_to_kp[chapterKey] || [];
  kpIds.forEach(id => {
    document.querySelectorAll(`.kp-item[data-kp-id="${id}"]`).forEach(el =>
      el.classList.add('highlight'));
  });
  const first = document.querySelector('.kp-item.highlight');
  if (first) first.scrollIntoView({block: 'center', behavior: 'smooth'});
}

// ─── search ──────────────────────────────────────────────────
document.getElementById('search').oninput = (e) => {
  const q = e.target.value.trim().toLowerCase();
  const items = [
    ...document.querySelectorAll('.kp-item'),
    ...document.querySelectorAll('.map-row'),
  ];
  if (!q) { items.forEach(el => el.classList.remove('hidden')); return; }
  items.forEach(el => {
    const hit = (el.dataset.searchable || '').includes(q);
    el.classList.toggle('hidden', !hit);
  });
};
document.getElementById('clear').onclick = () => {
  document.getElementById('search').value = '';
  document.querySelectorAll('.hidden').forEach(el => el.classList.remove('hidden'));
  clearHighlight();
};

// ─── tabs ────────────────────────────────────────────────────
document.querySelectorAll('#kp-tabs .tab').forEach(tab => {
  tab.onclick = () => {
    document.querySelectorAll('#kp-tabs .tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    renderKPs(tab.dataset.level1);
  };
});

// ─── boot ────────────────────────────────────────────────────
document.getElementById('stats').textContent =
  `${DATA.knowledge_points.length} 个 KP · ${Object.keys(DATA.chapter_to_kp).length} 条映射 · ` +
  `${Object.values(DATA.counts).reduce((a, b) => a + b, 0)} 题`;
document.getElementById('kp-count').textContent = `(${DATA.knowledge_points.length})`;
document.getElementById('map-count').textContent = `(${Object.keys(DATA.chapter_to_kp).length})`;

renderKPs('all');
renderMappings();
</script>

</body>
</html>
"""


def main() -> None:
    data = load_data()
    html = HTML_TEMPLATE.replace(
        "__NOTE__", data["note"].replace("<", "&lt;").replace(">", "&gt;")
    ).replace(
        "__DATA_JSON__", json.dumps({
            "knowledge_points": data["knowledge_points"],
            "chapter_to_kp":    data["chapter_to_kp"],
            "reverse":          data["reverse"],
            "counts":           data["counts"],
        }, ensure_ascii=False)
    )
    OUT.write_text(html, encoding="utf-8")
    print(f"✓ wrote {OUT}   ({OUT.stat().st_size / 1024:.1f} KB)")
    print(f"  双击打开或用浏览器访问 file://{OUT.absolute().as_posix()}")


if __name__ == "__main__":
    main()
