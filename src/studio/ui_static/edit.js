/* Reelsmith UI, part 3: editing. Timeline trim/move/split/delete, undo/redo, property forms,
   a live composite view (instant, approximate) and a crop tool. Every change rewrites the EDL
   through /api/edl/save, so Claude and the page always share one document. */
"use strict";

Object.assign(I18N.en, {
  live: "Live", liveBadge: "live view: instant approximation (the render is exact)", undo: "Undo", redo: "Redo",
  split: "Split", del: "Delete", addText: "+ Text", trimStart: "Trim start here", trimEnd: "Trim end here", crop: "Crop",
  conflict: "The EDL changed elsewhere (Claude?): reloaded, try again", newText: "New text",
  timing: "Timing", frameSec: "Frame", colorSec: "Color", sound: "Audio", transitionSec: "Transition", content: "Text",
  position: "Position", style: "Style", toPlayhead: "Set to playhead", editCrop: "Edit crop", resetCrop: "Reset",
  apply: "Apply", aspect: "Aspect", free: "Free", outputAr: "Output", json: "EDL entry",
  editHints: "<kbd>B</kbd> split · <kbd>Q</kbd>/<kbd>W</kbd> trim to playhead · <kbd>Del</kbd> delete · <kbd>T</kbd> text · <kbd>⌘Z</kbd> undo · drag edges to trim, drag blocks to move",
});
Object.assign(I18N.vi, {
  live: "Live", liveBadge: "xem nhanh: gần đúng, bản render mới là chính xác", undo: "Hoàn tác", redo: "Làm lại",
  split: "Cắt đôi", del: "Xoá", addText: "+ Chữ", trimStart: "Cắt đầu tới playhead", trimEnd: "Cắt đuôi tới playhead", crop: "Crop",
  conflict: "EDL vừa được sửa ở nơi khác (Claude?): đã tải lại, hãy thử lại", newText: "Chữ mới",
  timing: "Thời gian", frameSec: "Khung hình", colorSec: "Màu sắc", sound: "Âm thanh", transitionSec: "Chuyển cảnh", content: "Nội dung",
  position: "Vị trí", style: "Kiểu chữ", toPlayhead: "Lấy theo playhead", editCrop: "Sửa crop", resetCrop: "Bỏ crop",
  apply: "Áp dụng", aspect: "Tỉ lệ", free: "Tự do", outputAr: "Theo khung xuất", json: "Mục EDL",
  editHints: "<kbd>B</kbd> cắt đôi · <kbd>Q</kbd>/<kbd>W</kbd> cắt tới playhead · <kbd>Del</kbd> xoá · <kbd>T</kbd> thêm chữ · <kbd>⌘Z</kbd> hoàn tác · kéo mép để cắt, kéo khối để di chuyển",
});
const LBL = {
  en: { in: "In (source)", out: "Out (source)", speed: "Speed", fit: "Fit", zoom: "Zoom", "focus.0": "Focus X", "focus.1": "Focus Y",
    "grade.brightness": "Brightness", "grade.contrast": "Contrast", "grade.saturation": "Saturation", "grade.gamma": "Gamma",
    volume: "Volume", mute: "Mute", "fade.in": "Fade in (s)", "fade.out": "Fade out (s)", "transition.type": "Type",
    "transition.duration": "Duration (s)", duration: "Duration (s)", color: "Color", text: "Text", start: "Start", end: "End",
    x: "X", y: "Y", anchor: "Anchor", align: "Align", max_width: "Max width", size: "Size", stroke: "Outline", stroke_width: "Outline width",
    box: "Box", shadow: "Shadow", case: "Case", width: "Width", opacity: "Opacity", at: "Starts at", loop: "Loop",
    fade_in: "Fade in (s)", fade_out: "Fade out (s)", duck: "Duck under speech", captions: "No captions" },
  vi: { in: "Vào (nguồn)", out: "Ra (nguồn)", speed: "Tốc độ", fit: "Cách lấp khung", zoom: "Phóng to", "focus.0": "Tâm X", "focus.1": "Tâm Y",
    "grade.brightness": "Độ sáng", "grade.contrast": "Tương phản", "grade.saturation": "Độ bão hoà", "grade.gamma": "Gamma",
    volume: "Âm lượng", mute: "Tắt tiếng", "fade.in": "Hiện dần (s)", "fade.out": "Mờ dần (s)", "transition.type": "Kiểu",
    "transition.duration": "Thời lượng (s)", duration: "Thời lượng (s)", color: "Màu", text: "Nội dung", start: "Bắt đầu", end: "Kết thúc",
    x: "X", y: "Y", anchor: "Neo", align: "Căn lề", max_width: "Rộng tối đa", size: "Cỡ chữ", stroke: "Viền", stroke_width: "Độ dày viền",
    box: "Nền chữ", shadow: "Bóng", case: "Hoa/thường", width: "Chiều rộng", opacity: "Độ mờ", at: "Bắt đầu ở", loop: "Lặp lại",
    fade_in: "Hiện dần (s)", fade_out: "Mờ dần (s)", duck: "Tự giảm khi có tiếng nói", captions: "Không phụ đề" },
};
const L_ = (k) => LBL[LANG][k] ?? LBL.en[k] ?? k;

/* ---------- helpers ---------- */
const snap = (t, f = fps()) => Math.round(t * f) / f;
const r3 = (x) => Math.round(x * 1000) / 1000;
const r4 = (x) => Math.round(x * 10000) / 10000;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const LISTS = { clip: "clips", text: "text", images: "images", audio: "audio" };
const docEntry = (doc, sel) => (doc[LISTS[sel.type]] || [])[sel.index];
function getPath(o, path) { return path.split(".").reduce((a, k) => (a == null ? undefined : a[k]), o); }
function setPath(o, path, v, def) {
  const ks = path.split("."), stack = [];
  let cur = o;
  for (let i = 0; i < ks.length - 1; i++) {
    if (cur[ks[i]] == null || typeof cur[ks[i]] !== "object") cur[ks[i]] = /^\d+$/.test(ks[i + 1]) ? [0.5, 0.5] : {};
    stack.push([cur, ks[i]]);
    cur = cur[ks[i]];
  }
  const last = ks[ks.length - 1];
  const empty = v === "" || v === undefined || (def !== undefined && v === def);
  if (Array.isArray(cur)) cur[last] = empty ? def ?? 0.5 : v;
  else if (empty) delete cur[last];
  else cur[last] = v;
  for (let i = stack.length - 1; i >= 0; i--) {  // drop now-empty objects and the default focus
    const [p, k] = stack[i], val = p[k];
    if (Array.isArray(val) ? val.every((x) => x === 0.5) : val && typeof val === "object" && !Object.keys(val).length) delete p[k];
  }
}

/* ---------- saving, undo, redo ---------- */
const H = { undo: [], redo: [], chain: Promise.resolve() };
function commit(mutate, after) {
  H.chain = H.chain.then(async () => {
    if (!S.tl?.doc) return;
    const before = JSON.stringify(S.tl.doc);
    const doc = JSON.parse(before);
    mutate(doc);
    if (JSON.stringify(doc) === before) { renderTimeline(); return; }
    H.undo.push(before); if (H.undo.length > 200) H.undo.shift();
    H.redo = [];
    await saveDoc(doc);
    after?.();
  }).catch((e) => toast(e.message));
  return H.chain;
}
async function saveDoc(doc) {
  try {
    const r = await getJSON("/api/edl/save", { method: "POST", body: JSON.stringify({ edl: S.edl, base_mtime: S.ver?.edl_mtime, doc }) });
    S.ver.edl_mtime = r.edl_mtime;
  } catch (e) { toast(e.message === "conflict" ? T("conflict") : e.message); }
  await loadTimeline();
  syncHistoryButtons();
}
function undo() { H.chain = H.chain.then(async () => { const p = H.undo.pop(); if (!p) return; H.redo.push(JSON.stringify(S.tl.doc)); await saveDoc(JSON.parse(p)); }); }
function redo() { H.chain = H.chain.then(async () => { const n = H.redo.pop(); if (!n) return; H.undo.push(JSON.stringify(S.tl.doc)); await saveDoc(JSON.parse(n)); }); }

/* ---------- edit operations ---------- */
const clipUnder = (t = S.t) => { const c = clipAt(t); return c && t >= c.start && t < c.end ? c : null; };
const srcFps = (c) => c.src_fps || fps();

function splitAt(t = S.t) {
  const c = clipUnder(t);
  if (!c) return;
  const local = t - c.start, f = 1 / fps();
  if (local < f || c.end - t < f) return;
  commit((doc) => {
    const e = doc.clips[c.index], a = { ...e }, b = { ...e };
    delete b.transition;
    if (e.fade) {
      a.fade = { ...e.fade }; b.fade = { ...e.fade }; delete a.fade.out; delete b.fade.in;
      if (!Object.keys(a.fade).length) delete a.fade;
      if (!Object.keys(b.fade).length) delete b.fade;
    }
    if (c.kind === "video") { const cut = r3(snap(c.in + local * c.speed, srcFps(c))); a.out = cut; b.in = cut; }
    else { a.duration = r3(snap(local)); b.duration = r3(snap(c.end - c.start - local)); }
    doc.clips.splice(c.index, 1, a, b);
  }, () => { S.selected = { type: "clip", index: c.index + 1 }; renderInspector(); });
}
function trimToPlayhead(which) {
  const c = clipUnder();
  if (!c) return;
  const local = S.t - c.start;
  commit((doc) => {
    const e = doc.clips[c.index];
    if (c.kind === "video") {
      const v = r3(snap(c.in + local * c.speed, srcFps(c)));
      if (which === "start") { if (v > 0) e.in = v; } else e.out = v;
    } else if (which === "start") e.duration = r3(snap(c.end - c.start - local));
    else e.duration = r3(snap(local));
  }, () => { if (which === "start") setTime(c.start); });
}
function deleteSelected() {
  const s = S.selected;
  if (!s || !LISTS[s.type]) return;
  commit((doc) => { doc[LISTS[s.type]]?.splice(s.index, 1); }, () => { S.selected = null; renderInspector(); });
}
function addText() {
  const t0 = r3(snap(S.t)), t1 = r3(snap(Math.min(dur() || 3, S.t + 3)));
  let idx = 0;
  commit((doc) => { doc.text = doc.text || []; idx = doc.text.length; doc.text.push({ text: T("newText"), start: t0, end: Math.max(t1, r3(t0 + 1)) }); },
    () => { S.selected = { type: "text", index: idx }; renderInspector(); if (S.view !== "source") setView("source"); });
}

/* ---------- timeline: handles and dragging ---------- */
let suppressClick = false;
document.addEventListener("click", (e) => { if (suppressClick) { e.stopPropagation(); e.preventDefault(); suppressClick = false; } }, true);

const _renderTimeline = renderTimeline;
renderTimeline = function () {
  _renderTimeline();
  document.querySelectorAll(".blk[data-sel]").forEach((b) => {
    const [type, i] = b.dataset.sel.split(":");
    if (type === "captions" || b.classList.contains("audio")) return;  // A1 mirrors the clip; captions follow speech
    b.append(el("div", "hdl l"), el("div", "hdl r"));
    b.addEventListener("pointerdown", (e) => startDrag(e, b, type, +i));
  });
};

function startDrag(e, b, type, index) {
  if (e.button !== 0) return;
  const mode = e.target.classList.contains("l") ? "l" : e.target.classList.contains("r") ? "r" : "move";
  const it = type === "clip" ? S.tl.clips.find((c) => c.index === index) : (S.tl[LISTS[type]] || []).find((x) => x.index === index);
  if (!it) return;
  const x0 = e.clientX, pps = S.pps, left0 = it.start * pps, w0 = (it.end - it.start) * pps;
  let dt = 0, moved = false;
  b.setPointerCapture(e.pointerId);
  const mv = (ev) => {
    const dx = ev.clientX - x0;
    if (!moved && Math.abs(dx) < 4) return;
    moved = true;
    dt = snap(dx / pps);
    const d = dt * pps;
    b.classList.add("dragging");
    if (mode === "move") b.style.transform = `translateX(${d}px)`;
    else if (mode === "l") { b.style.left = left0 + d + "px"; b.style.width = Math.max(4, w0 - d) + "px"; }
    else b.style.width = Math.max(4, w0 + d) + "px";
    if (mode !== "move") setTime(mode === "l" ? it.start + dt : Math.max(it.start, it.end + dt - 1 / fps()));
  };
  b.addEventListener("pointermove", mv);
  b.addEventListener("pointerup", () => {
    b.removeEventListener("pointermove", mv);
    if (!moved) return;
    suppressClick = true; setTimeout(() => (suppressClick = false), 60);
    applyDrag(type, it, mode, dt);
  }, { once: true });
}

function applyDrag(type, it, mode, dt) {
  const f = 1 / fps();
  if (type === "clip") {
    if (mode === "move") {
      const mid = it.start + dt + (it.end - it.start) / 2;
      const to = S.tl.clips.filter((c) => c.index !== it.index && (c.start + c.end) / 2 < mid).length;
      return commit((doc) => { const [x] = doc.clips.splice(it.index, 1); doc.clips.splice(to, 0, x); },
        () => { S.selected = { type: "clip", index: to }; renderInspector(); });
    }
    return commit((doc) => {
      const e = doc.clips[it.index];
      if (it.kind === "video") {
        const sf = srcFps(it), minLen = f * it.speed;
        if (mode === "l") { const v = r3(snap(clamp(it.in + dt * it.speed, 0, it.out - minLen), sf)); if (v > 0) e.in = v; else delete e.in; }
        else {
          const v = r3(snap(clamp(it.out + dt * it.speed, it.in + minLen, it.src_duration || 1e9), sf));
          if (it.src_duration && v >= it.src_duration - 0.001) delete e.out; else e.out = v;
        }
      } else e.duration = r3(Math.max(f, snap((it.end - it.start) + (mode === "l" ? -dt : dt))));
    });
  }
  return commit((doc) => {
    const e = docEntry(doc, { type, index: it.index });
    if (!e) return;
    if (type === "audio") {
      if (mode === "move") e.at = r3(Math.max(0, it.start + dt));
      else if (mode === "l") {
        const d = clamp(dt, -Math.min(it.start, it.in), it.end - it.start - f);
        e.at = r3(it.start + d);
        if (it.in + d > 0) e.in = r3(it.in + d); else delete e.in;
      } else e.out = r3(Math.max(it.in + f, it.out + dt));
      return;
    }
    if (mode === "move") { const d = Math.max(-it.start, dt); e.start = r3(it.start + d); if (e.end != null) e.end = r3(it.end + d); }
    else if (mode === "l") e.start = r3(clamp(it.start + dt, 0, it.end - f));
    else e.end = r3(Math.max(it.start + f, it.end + dt));
  });
}

/* ---------- timeline toolbar and keys ---------- */
const tools = document.querySelector(".tl-tools");
const tb = (txt, title, fn) => { const b = el("button", null, txt); b.title = title; b.onclick = fn; return b; };
const bUndo = tb("↶", T("undo") + " (⌘Z)", undo), bRedo = tb("↷", T("redo") + " (⇧⌘Z)", redo);
tools.prepend(bUndo, bRedo, tb("✂ " + T("split"), T("split") + " (B)", () => splitAt()),
  tb("🗑", T("del") + " (Del)", deleteSelected), tb(T("addText"), T("addText") + " (T)", addText), el("span", "tl-sep"));
function syncHistoryButtons() { bUndo.disabled = !H.undo.length; bRedo.disabled = !H.redo.length; }
syncHistoryButtons();

document.addEventListener("keydown", (e) => {
  if (e.target.matches("input, select, textarea") || document.querySelector("dialog[open]") || E.src || cropState) return;
  const k = e.key.toLowerCase(), mod = e.metaKey || e.ctrlKey;
  if (mod && k === "z") { e.preventDefault(); e.shiftKey ? redo() : undo(); return; }
  if (mod && k === "y") { e.preventDefault(); redo(); return; }
  if (mod || e.altKey) return;
  if (k === "b") { e.preventDefault(); splitAt(); }
  else if (k === "q") { e.preventDefault(); trimToPlayhead("start"); }
  else if (k === "w") { e.preventDefault(); trimToPlayhead("end"); }
  else if (k === "t") { e.preventDefault(); addText(); }
  else if (k === "delete" || k === "backspace") { e.preventDefault(); deleteSelected(); }
});

/* ---------- property forms ---------- */
const XF = ["fade", "fadeblack", "fadewhite", "dissolve", "wipeleft", "wiperight", "wipeup", "wipedown", "slideleft", "slideright",
  "slideup", "slidedown", "smoothleft", "smoothright", "circleopen", "circleclose", "radial", "pixelize", "zoomin", "hblur",
  "diagtl", "diagtr", "diagbl", "diagbr"];
const ANCH = ["center", "top", "bottom", "left", "right", "top-left", "top-right", "bottom-left", "bottom-right"];
const R = (min, max, step, def) => ({ min, max, step, def });
const FRAME = ["frameSec", [["fit", "select", { options: ["", "cover", "contain", "blur", "fill"] }], ["zoom", "number", R(1, 4, 0.01, 1)],
  ["focus.0", "range", R(0, 1, 0.01, 0.5)], ["focus.1", "range", R(0, 1, 0.01, 0.5)], ["crop", "crop"]]];
const GRADE = ["colorSec", [["grade.brightness", "range", R(-0.3, 0.3, 0.01, 0)], ["grade.contrast", "range", R(0.5, 1.5, 0.01, 1)],
  ["grade.saturation", "range", R(0, 2, 0.01, 1)], ["grade.gamma", "range", R(0.5, 1.8, 0.01, 1)]]];
const FADES = [["fade.in", "number", R(0, 10, 0.1)], ["fade.out", "number", R(0, 10, 0.1)]];
const TRANS = ["transitionSec", [["transition.type", "select", { options: ["", ...XF] }], ["transition.duration", "number", R(0.04, 3, 0.04, 0.5)]]];
const SCHEMAS = {
  video: [["timing", [["in", "srcTime"], ["out", "srcTime"], ["speed", "number", R(0.1, 8, 0.05, 1)]]], FRAME, GRADE,
    ["sound", [["volume", "range", R(0, 2, 0.05, 1)], ["mute", "checkbox"], ...FADES, ["captions", "checkbox", { invert: true }]]], TRANS],
  image: [["timing", [["duration", "number", R(0.04, 600, 0.04, 3)], ...FADES]], FRAME, GRADE, TRANS],
  color: [["timing", [["duration", "number", R(0.04, 600, 0.04, 2)]]], ["frameSec", [["color", "color"]]], TRANS],
  text: [["content", [["text", "textarea"]]], ["timing", [["start", "tlTime"], ["end", "tlTime"]]],
    ["position", [["x", "range", R(0, 1, 0.005, 0.5)], ["y", "range", R(0, 1, 0.005, 0.5)], ["anchor", "select", { options: ["", ...ANCH] }],
      ["align", "select", { options: ["", "left", "center", "right"] }], ["max_width", "range", R(0.2, 1, 0.01, 0.86)]]],
    ["style", [["size", "number", R(0.01, 400, 0.005, 0.06)], ["color", "color", { def: "#FFFFFF" }], ["stroke", "color", { placeholder: "#000000 / none" }],
      ["stroke_width", "number", R(0, 0.4, 0.01, 0.08)], ["box", "color", { placeholder: "#000000A0" }], ["shadow", "color", { placeholder: "#00000099" }],
      ["case", "select", { options: ["", "upper", "lower"] }]]]],
  images: [["timing", [["start", "tlTime"], ["end", "tlTime"]]], ["position", [["x", "range", R(0, 1, 0.005, 0.5)], ["y", "range", R(0, 1, 0.005, 0.5)],
    ["anchor", "select", { options: ["", ...ANCH] }], ["width", "range", R(0.02, 1, 0.01)], ["opacity", "range", R(0, 1, 0.01, 1)]]]],
  audio: [["timing", [["at", "tlTime"], ["in", "srcTime"], ["out", "srcTime"], ["loop", "checkbox"]]],
    ["sound", [["volume", "range", R(0, 2, 0.05, 1)], ["fade_in", "number", R(0, 30, 0.1)], ["fade_out", "number", R(0, 30, 0.1)], ["duck", "checkbox"]]]],
};

function field(sel, it, [key, kind, o = {}]) {
  const row = el("div", "f-row");
  row.append(el("label", null, L_(key)));
  const entry = it.entry || {};
  let cur = getPath(entry, key);
  if (key === "in" && cur == null) cur = it.in ?? 0;
  if (key === "out" && cur == null) cur = it.out;
  const set = (v, final = true) => {
    if (!final) { setPath(entry, key, v, o.def); requestLive(); return; }  // preview only; saved on change
    commit((doc) => setPath(docEntry(doc, sel), key, v, o.def));
  };
  const num = (v) => (v === "" ? "" : Number(v));
  let input;
  if (kind === "number") {
    input = el("input"); input.type = "number"; Object.assign(input, { min: o.min ?? "", max: o.max ?? "", step: o.step ?? "any" });
    input.value = cur ?? ""; input.placeholder = o.def ?? "";
    input.onchange = () => set(num(input.value));
  } else if (kind === "range") {
    const wrap = el("div", "f-range");
    input = el("input"); input.type = "range"; Object.assign(input, { min: o.min, max: o.max, step: o.step });
    input.value = cur ?? o.def ?? o.min;
    const out = el("input"); out.type = "number"; out.step = o.step; out.value = cur ?? ""; out.placeholder = o.def ?? "";
    input.oninput = () => { out.value = input.value; set(Number(input.value), false); };
    input.onchange = () => set(Number(input.value));
    out.onchange = () => { input.value = out.value || o.def || 0; set(num(out.value)); };
    wrap.append(input, out); row.append(wrap); return row;
  } else if (kind === "select") {
    input = el("select");
    for (const v of o.options) { const op = el("option", null, v || "–"); op.value = v; input.append(op); }
    input.value = cur ?? "";
    input.onchange = () => set(input.value);
  } else if (kind === "checkbox") {
    input = el("input"); input.type = "checkbox";
    input.checked = o.invert ? cur === false : !!cur;
    input.onchange = () => set(o.invert ? (input.checked ? false : "") : (input.checked ? true : ""));
    row.classList.add("f-check");
  } else if (kind === "textarea") {
    input = el("textarea"); input.rows = 2; input.value = cur ?? "";
    input.oninput = () => set(input.value, false);
    input.onchange = () => set(input.value);
  } else if (kind === "color") {
    const wrap = el("div", "f-color");
    const txt = el("input"); txt.type = "text"; txt.value = cur === null ? "none" : cur ?? ""; txt.placeholder = o.placeholder || o.def || "";
    const pick = el("input"); pick.type = "color"; pick.value = /^#[0-9a-f]{6}/i.test(cur || "") ? cur.slice(0, 7) : "#ffffff";
    txt.onchange = () => set(txt.value.trim().toLowerCase() === "none" ? null : txt.value.trim());
    pick.oninput = () => { txt.value = pick.value + (/^#[0-9a-f]{8}$/i.test(cur || "") ? cur.slice(7) : ""); set(txt.value, false); };
    pick.onchange = () => set(txt.value);
    wrap.append(pick, txt); row.append(wrap); return row;
  } else if (kind === "srcTime" || kind === "tlTime") {
    const wrap = el("div", "f-time");
    const rate = kind === "srcTime" ? it.src_fps || fps() : fps(), step = 1 / rate;
    input = el("input"); input.type = "number"; input.step = step.toFixed(5); input.min = 0; input.value = cur != null ? r3(cur) : "";
    if (key === "end") input.placeholder = fmt(dur());
    const go = (v) => set(v === "" ? "" : r3(Math.max(0, v)));
    input.onchange = () => go(input.value === "" ? "" : snap(Number(input.value), rate));
    const minus = el("button", "small", "−1f"), plus = el("button", "small", "+1f"), ph = el("button", "small", "⌖");
    minus.onclick = () => go(snap((Number(input.value) || 0) - step, rate));
    plus.onclick = () => go(snap((Number(input.value) || 0) + step, rate));
    ph.title = T("toPlayhead");
    ph.onclick = () => {
      if (kind === "tlTime") return go(snap(S.t));
      if (sel.type === "clip") { if (S.t >= it.start && S.t < it.end) go(snap(srcTime(it, S.t), rate)); }
      else go(snap(it.in + Math.max(0, S.t - it.start), rate));
    };
    wrap.append(input, minus, plus, ph); row.append(wrap); return row;
  } else if (kind === "crop") {
    const wrap = el("div", "f-crop");
    const c = getPath(entry, "crop");
    wrap.append(el("span", "mono", c ? c.map((v) => v.toFixed(3)).join(", ") : "–"));
    const eb = el("button", "small", "⬚ " + T("editCrop")); eb.onclick = () => enterCrop(sel.index);
    wrap.append(eb);
    if (c) { const rb = el("button", "small", T("resetCrop")); rb.onclick = () => set(""); wrap.append(rb); }
    row.append(wrap); return row;
  }
  row.append(input);
  return row;
}

renderInspector = function () {
  const box = $("#inspector"), tl = S.tl;
  box.replaceChildren();
  if (!tl) return;
  const msgs = [...(tl.errors || []).map((m) => ["err", m]), ...(tl.warnings || []).map((m) => ["warn", m])];
  if (msgs.length) { box.append(el("h3", null, T("errors"))); for (const [k, m] of msgs) box.append(el("div", "msg " + k, m)); }
  const it = findSelected(), s = S.selected;
  if (it?.render) { box.append(el("h3", null, T("renderMsg")), el("pre", null, S.ver?.render?.message || "–")); return; }
  if (!it) {
    box.append(el("h3", null, tl.path || tl.name), el("p", "hint", T("selectHint")));
    const k = el("p", "hint"); k.innerHTML = T("keys") + "<br>" + T("editHints"); box.append(k);
    return;
  }
  const kind = s.type === "clip" ? it.kind : s.type;
  const title = { clip: `${T("clip")} #${it.index} · ${it.label}`, audio: `${T("audio")} [${it.index}] · ${it.label}`, text: `${T("text")} [${it.index}]`,
    images: `${T("images")} [${it.index}]`, captions: `${T("captions")} ${s.index + 1}` }[s.type];
  box.append(el("h3", null, title));
  const dl = el("dl");
  dl.append(el("dt", null, T("tlRange")), el("dd", "mono", `${fmt(it.start)} → ${fmt(it.end)} (${(it.end - it.start).toFixed(2)}s)`));
  box.append(dl);
  if (LISTS[s.type]) {
    const acts = el("div", "f-acts");
    if (s.type === "clip") {
      acts.append(tb("✂ " + T("split"), "B", () => splitAt()), tb("⇤ " + T("trimStart"), "Q", () => trimToPlayhead("start")),
        tb(T("trimEnd") + " ⇥", "W", () => trimToPlayhead("end")));
      if (it.kind !== "color") acts.append(tb("⬚ " + T("crop"), "", () => enterCrop(it.index)));
    }
    acts.append(tb("🗑 " + T("del"), "Del", deleteSelected));
    box.append(acts);
  }
  for (const [secKey, fields] of SCHEMAS[kind] || []) {
    const sec = el("details", "f-sec");
    sec.open = !["transitionSec", "colorSec"].includes(secKey) || fields.some(([k]) => getPath(it.entry || {}, k) != null);
    sec.append(el("summary", null, T(secKey)));
    for (const f of fields) {
      if (f[0].startsWith("transition.") && it.index === 0 && s.type === "clip") continue;
      sec.append(field(s, it, f));
    }
    if (sec.children.length > 1) box.append(sec);
  }
  const raw = el("details", "f-sec"); raw.append(el("summary", null, T("json")));
  const pre = el("pre", "mono"); pre.innerHTML = jsonHtml(it.entry ?? { text: it.text }); raw.append(pre);
  box.append(raw);
};

/* ---------- live composite view ---------- */
const liveCv = el("canvas", "live");
$("#screen").append(liveCv);
document.querySelector('#viewSeg button[data-v="source"]').textContent = T("live");
const _renderViewer = renderViewer;
renderViewer = function (reload) {
  _renderViewer(reload);
  frame.hidden = true;
  liveCv.hidden = S.view !== "source" || !!cropState;
  if (S.view === "source") $("#badge").textContent = T("liveBadge");
  requestLive();
};
updateSourceFrame = function () { requestLive(); };

const imgCache = new Map();
let lastImg = null, liveRaf = 0;
function getImg(url) {
  let im = imgCache.get(url);
  if (!im) {
    im = new Image(); im.onload = requestLive; im.src = url; imgCache.set(url, im);
    if (imgCache.size > 400) imgCache.delete(imgCache.keys().next().value);
  }
  return im.complete && im.naturalWidth ? im : null;
}
function requestLive() { if (!liveRaf) liveRaf = requestAnimationFrame(() => { liveRaf = 0; drawLive(); }); }
window.addEventListener("resize", requestLive);

function drawLive() {
  if (S.view !== "source" || !S.tl || cropState || liveCv.hidden) return;
  const o = S.tl.output, box = $("#screen").getBoundingClientRect(), ar = o.width / o.height;
  let W = box.width - 16, Hh = W / ar;
  if (Hh > box.height - 16) { Hh = box.height - 16; W = Hh * ar; }
  if (W < 10 || Hh < 10) return;
  const dpr = window.devicePixelRatio || 1;
  liveCv.style.width = W + "px"; liveCv.style.height = Hh + "px";
  liveCv.width = Math.round(W * dpr); liveCv.height = Math.round(Hh * dpr);
  const g = liveCv.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.fillStyle = o.bg || "#000"; g.fillRect(0, 0, W, Hh);
  const t = S.t, c = clipAt(t);
  if (c) {
    const e = c.entry || {};
    if (c.kind === "color") { g.fillStyle = c.color; g.fillRect(0, 0, W, Hh); }
    else {
      const st = c.kind === "video" ? srcTime(c, t) : 0;
      let im = getImg(`/api/thumb?src=${enc(c.src)}&t=${(Math.round(st * 100) / 100).toFixed(2)}&h=720`);
      if (im) lastImg = { key: c.index, im }; else if (lastImg?.key === c.index) im = lastImg.im;
      if (im) drawClip(g, im, e, c, W, Hh, o);
    }
    const local = t - c.start, fd = e.fade || {};
    let black = 0;
    if (fd.in && local < fd.in) black = Math.max(black, 1 - local / fd.in);
    if (fd.out && c.end - t < fd.out) black = Math.max(black, 1 - (c.end - t) / fd.out);
    if (o.fade_in && t < o.fade_in) black = Math.max(black, 1 - t / o.fade_in);
    if (o.fade_out && dur() - t < o.fade_out) black = Math.max(black, 1 - (dur() - t) / o.fade_out);
    if (black > 0) { g.fillStyle = `rgba(0,0,0,${black})`; g.fillRect(0, 0, W, Hh); }
  }
  for (const im of S.tl.images || []) if (t >= im.start && t < im.end) drawOverlayImage(g, im.entry, W, Hh);
  for (const tx of S.tl.text || []) if (t >= tx.start && t < tx.end) drawText(g, tx.entry, W, Hh, {});
  const cap = (S.tl.captions || []).find((ch) => t >= ch.start && t < ch.end);
  if (cap) {
    const vert = o.height > o.width;
    const base = vert ? { y: 0.7, size: 0.075, stroke_width: 0.11, max_width: 0.84 } : { y: 0.86, size: 0.055, stroke_width: 0.09, max_width: 0.8 };
    drawText(g, { ...(S.tl.doc?.captions?.style || {}), text: cap.text }, W, Hh, base);
  }
}

function gradeFilter(gr) {
  const parts = [];
  if (gr.brightness) parts.push(`brightness(${(1 + gr.brightness * 1.6).toFixed(3)})`);
  if (gr.contrast != null && gr.contrast !== 1) parts.push(`contrast(${gr.contrast})`);
  if (gr.saturation != null && gr.saturation !== 1) parts.push(`saturate(${gr.saturation})`);
  return parts.join(" ") || "none";
}
function drawClip(g, im, e, c, W, Hh, o) {
  const sw = im.naturalWidth, sh = im.naturalHeight;
  const [cx, cy, cw, ch] = e.crop || [0, 0, 1, 1];
  const sx = cx * sw, sy = cy * sh, sW = Math.max(1, cw * sw), sH = Math.max(1, ch * sh);
  const fit = e.fit || o.fit || "cover";
  let z = 1;
  if (typeof e.zoom === "number") z = e.zoom;
  else if (e.zoom && typeof e.zoom === "object") {
    const p = clamp((S.t - c.start) / (c.end - c.start || 1), 0, 1), a = e.zoom.from ?? 1, b = e.zoom.to ?? 1.2;
    z = a + (b - a) * p;
  }
  const [fx, fy] = e.focus || [0.5, 0.5];
  const filt = gradeFilter({ ...(o.grade || {}), ...(e.grade || {}) });
  const cover = (zz) => {
    const s = Math.max(W / sW, Hh / sH) * zz, dw = sW * s, dh = sH * s;
    g.drawImage(im, sx, sy, sW, sH, clamp(W / 2 - fx * dw, W - dw, 0), clamp(Hh / 2 - fy * dh, Hh - dh, 0), dw, dh);
  };
  const contain = () => { const s = Math.min(W / sW, Hh / sH), dw = sW * s, dh = sH * s; g.drawImage(im, sx, sy, sW, sH, (W - dw) / 2, (Hh - dh) / 2, dw, dh); };
  g.filter = filt;
  if (fit === "contain") contain();
  else if (fit === "blur") { g.filter = (filt === "none" ? "" : filt + " ") + "blur(16px)"; cover(1.1); g.filter = filt; contain(); }
  else if (fit === "fill") g.drawImage(im, sx, sy, sW, sH, 0, 0, W, Hh);
  else cover(z);
  g.filter = "none";
}
function anchorOffset(a, w, h) {
  return [a.includes("left") ? 0 : a.includes("right") ? -w : -w / 2, a.includes("top") ? 0 : a.includes("bottom") ? -h : -h / 2];
}
function drawOverlayImage(g, e, W, Hh) {
  const im = getImg(`/api/thumb?src=${enc(e.src)}&t=0&h=480`);
  if (!im) return;
  const wf = e.width ?? 0.2, w = wf <= 1 ? wf * W : wf * (W / S.tl.output.width), h = (w * im.naturalHeight) / im.naturalWidth;
  const [ox, oy] = anchorOffset(e.anchor || "center", w, h);
  g.globalAlpha = e.opacity ?? 1;
  g.drawImage(im, (e.x ?? 0.5) * W + ox, (e.y ?? 0.5) * Hh + oy, w, h);
  g.globalAlpha = 1;
}
function drawText(g, e, W, Hh, base) {
  const st = { x: 0.5, y: 0.5, anchor: "center", align: "center", size: 0.06, color: "#FFFFFF", stroke: "#000000", stroke_width: 0.08,
    max_width: 0.86, line_spacing: 1.15, ...base, ...e };
  const px = st.size <= 1 ? st.size * Math.min(W, Hh) : st.size * (W / S.tl.output.width);
  g.font = `700 ${px}px "Be Vietnam Pro", "Helvetica Neue", Arial, sans-serif`;
  let text = String(st.text ?? "");
  if (st.case === "upper") text = text.toUpperCase(); else if (st.case === "lower") text = text.toLowerCase();
  const maxW = st.max_width * W, lines = [];
  for (const para of text.split("\n")) {
    let line = "";
    for (const w of para.split(" ")) {
      const next = line ? line + " " + w : w;
      if (line && g.measureText(next).width > maxW) { lines.push(line); line = w; } else line = next;
    }
    lines.push(line);
  }
  const lh = px * st.line_spacing, bw = Math.max(...lines.map((l) => g.measureText(l).width)), bh = lh * lines.length;
  const [ox, oy] = anchorOffset(st.anchor, bw, bh);
  const x0 = st.x * W + ox, y0 = st.y * Hh + oy;
  if (st.box) {
    const pad = (st.box_padding ?? 0.35) * px;
    g.fillStyle = st.box; g.beginPath();
    g.roundRect(x0 - pad, y0 - pad * 0.7, bw + pad * 2, bh + pad * 1.4, (st.box_radius ?? 0.3) * px); g.fill();
  }
  g.textBaseline = "top"; g.lineJoin = "round";
  lines.forEach((l, i) => {
    const lw = g.measureText(l).width;
    const lx = st.align === "left" ? x0 : st.align === "right" ? x0 + bw - lw : x0 + (bw - lw) / 2, ly = y0 + i * lh + (lh - px) / 2;
    if (st.shadow) { g.shadowColor = st.shadow; g.shadowBlur = px * 0.2; g.shadowOffsetY = px * 0.05; }
    if (st.stroke) { g.strokeStyle = st.stroke; g.lineWidth = st.stroke_width * px * 2; g.strokeText(l, lx, ly); }
    g.shadowColor = "transparent";
    g.fillStyle = st.color; g.fillText(l, lx, ly);
  });
}

/* ---------- crop tool ---------- */
let cropState = null;
const ASPECTS = [["free", null], ["output", "out"], ["9:16", 9 / 16], ["16:9", 16 / 9], ["1:1", 1], ["4:5", 4 / 5]];
function enterCrop(index) {
  const c = S.tl.clips.find((x) => x.index === index);
  if (!c || c.kind === "color") return;
  pause();
  if (S.view !== "source") setView("source");
  const t = S.t >= c.start && S.t < c.end ? S.t : c.start + 0.01;
  setTime(t);
  const st = c.kind === "video" ? srcTime(c, t) : 0;
  cropState = { c, rect: (c.entry.crop || [0, 0, 1, 1]).slice(), aspect: null };
  liveCv.hidden = true;
  const ui = el("div", "cropui");
  ui.innerHTML = `<div class="crop-stage"><img alt=""><div class="cropbox"><i class="ch nw"></i><i class="ch ne"></i><i class="ch sw"></i><i class="ch se"></i></div></div>
    <div class="crop-bar"><label></label><select></select><span class="mono crop-val"></span><div class="spacer"></div>
    <button class="c-reset"></button><button class="c-cancel"></button><button class="primary c-apply"></button></div>`;
  $("#screen").append(ui);
  cropState.ui = ui;
  const img = ui.querySelector("img"), sel = ui.querySelector("select");
  ui.querySelector("label").textContent = T("aspect");
  for (const [k] of ASPECTS) {
    const op = el("option", null, k === "free" ? T("free") : k === "output" ? `${T("outputAr")} (${S.tl.output.width}:${S.tl.output.height})` : k);
    op.value = k; sel.append(op);
  }
  ui.querySelector(".c-reset").textContent = T("resetCrop");
  ui.querySelector(".c-cancel").textContent = T("cancel");
  ui.querySelector(".c-apply").textContent = T("apply");
  ui.querySelector(".c-cancel").onclick = exitCrop;
  ui.querySelector(".c-reset").onclick = () => { cropState.rect = [0, 0, 1, 1]; sel.value = "free"; cropState.aspect = null; layoutCrop(); };
  ui.querySelector(".c-apply").onclick = () => {
    const r = cropState.rect.map(r4), full = r[0] < 0.001 && r[1] < 0.001 && r[2] > 0.999 && r[3] > 0.999, idx = c.index;
    exitCrop();
    commit((doc) => { if (full) delete doc.clips[idx].crop; else doc.clips[idx].crop = r; });
  };
  sel.onchange = () => {
    const a = ASPECTS.find(([k]) => k === sel.value)[1];
    cropState.aspect = a === "out" ? S.tl.output.width / S.tl.output.height : a;
    if (cropState.aspect) fitAspect();
    layoutCrop();
  };
  img.onload = layoutCrop;
  img.src = `/api/thumb?src=${enc(c.src)}&t=${st.toFixed(2)}&h=1080`;
  ui.querySelector(".cropbox").addEventListener("pointerdown", (e) =>
    cropDrag(e, e.target.classList.contains("ch") ? [...e.target.classList].find((x) => x !== "ch") : "move"));
}
function exitCrop() { cropState?.ui.remove(); cropState = null; liveCv.hidden = S.view !== "source"; requestLive(); }
function cropImgRect() {
  const ui = cropState.ui, img = ui.querySelector("img"), stage = ui.querySelector(".crop-stage").getBoundingClientRect();
  const iw = img.naturalWidth || 16, ih = img.naturalHeight || 9, s = Math.min(stage.width / iw, stage.height / ih);
  return { x: (stage.width - iw * s) / 2, y: (stage.height - ih * s) / 2, w: iw * s, h: ih * s, iw, ih };
}
function fitAspect() {  // the largest rect of the chosen aspect, centred on the current one
  const { iw, ih } = cropImgRect(), A = cropState.aspect, [x, y, w, h] = cropState.rect;
  const cx = x + w / 2, cy = y + h / 2;
  let nw = 1, nh = iw / A / ih;
  if (nh > 1) { nh = 1; nw = (ih * A) / iw; }
  cropState.rect = [clamp(cx - nw / 2, 0, 1 - nw), clamp(cy - nh / 2, 0, 1 - nh), nw, nh];
}
function layoutCrop() {
  if (!cropState) return;
  const ui = cropState.ui, img = ui.querySelector("img"), r = cropImgRect();
  Object.assign(img.style, { left: r.x + "px", top: r.y + "px", width: r.w + "px", height: r.h + "px" });
  const [x, y, w, h] = cropState.rect, b = ui.querySelector(".cropbox");
  Object.assign(b.style, { left: r.x + x * r.w + "px", top: r.y + y * r.h + "px", width: w * r.w + "px", height: h * r.h + "px" });
  ui.querySelector(".crop-val").textContent = `${Math.round(w * r.iw)}×${Math.round(h * r.ih)} · [${cropState.rect.map((v) => v.toFixed(3)).join(", ")}]`;
}
function cropDrag(e, mode) {
  e.preventDefault();
  const r = cropImgRect(), r0 = cropState.rect.slice(), x0 = e.clientX, y0 = e.clientY, tgt = e.target;
  tgt.setPointerCapture(e.pointerId);
  const A = cropState.aspect, k = A ? r.iw / r.ih / A : null;  // in fractions of the frame: h = w * k
  const mv = (ev) => {
    const dx = (ev.clientX - x0) / r.w, dy = (ev.clientY - y0) / r.h;
    let [x, y, w, h] = r0;
    if (mode === "move") { x = clamp(x + dx, 0, 1 - w); y = clamp(y + dy, 0, 1 - h); }
    else {
      const right = x + w, bottom = y + h, min = 0.03;
      if (mode.includes("w")) { x = clamp(x + dx, 0, right - min); w = right - x; } else w = clamp(w + dx, min, 1 - x);
      if (mode.includes("n")) { y = clamp(y + dy, 0, bottom - min); h = bottom - y; } else h = clamp(h + dy, min, 1 - y);
      if (k) {
        h = w * k;
        if (mode.includes("n")) y = bottom - h;
        if (y < 0 || y + h > 1) {
          h = mode.includes("n") ? bottom : 1 - y; w = h / k;
          if (mode.includes("w")) x = right - w;
          if (mode.includes("n")) y = bottom - h;
        }
      }
    }
    cropState.rect = [x, y, w, h];
    layoutCrop();
  };
  tgt.addEventListener("pointermove", mv);
  tgt.addEventListener("pointerup", () => tgt.removeEventListener("pointermove", mv), { once: true });
}
window.addEventListener("resize", () => cropState && layoutCrop());
document.addEventListener("keydown", (e) => {
  if (!cropState) return;
  if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); exitCrop(); }
  else if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); cropState.ui.querySelector(".c-apply").click(); }
}, true);

if (S.tl) { renderTimeline(); renderViewer(false); renderInspector(); }
