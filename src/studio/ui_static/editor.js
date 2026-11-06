/* Reelsmith UI, part 2: media library, source monitor, import, export and jobs.
   Runs after index.html's script and uses its globals (S, T, I18N, $, el, enc, fmt, getJSON, TOKEN, ...). */
"use strict";

Object.assign(I18N.en, {
  import: "Import", export: "Export", media: "Media", all: "All", videos: "Video", audios: "Audio", imgs: "Images",
  libEmpty: "No media yet.<br>Drop files anywhere on this page, or press <b>Import</b>.",
  analyzing: "analyzing", addClip: "Add to timeline", addAudio: "Add as audio track", close: "Close",
  setIn: "[ In", setOut: "Out ]", added: "Added to {where}", whereClips: "the video track", whereAudio: "an audio track",
  dropHere: "Drop to import into the workspace",
  impTitle: "Import media", impPick: "Choose files… (video, audio, images)", or: "or",
  impPath: "Use files already on this Mac (path to a file or folder, nothing is copied)",
  impTr: "Transcribe speech (for captions)", lang: "Language", auto: "Auto-detect", cancel: "Cancel", impGo: "Import path",
  impNote: "Uploaded files are copied into footage/ or audio/ of the workspace, then analyzed (scenes, loudness, silences).",
  expTitle: "Export", expVideo: "Video", expAudio: "Audio", expSrt: "Captions .srt", frameFmt: "Frame", quality: "Quality",
  qHigh: "High", qStd: "Standard", qSmall: "Small file", asEdl: "As in the EDL", afmt: "Format", onlyRange: "Export only a range",
  from: "From (s)", to: "To (s)", expGo: "Export",
  expNote: "Files are written to renders/ in the workspace. Audio export renders the full mix first.",
  jUpload: "Uploading", jImport: "Import", jExport: "Export", download: "Download", reveal: "Show in Finder",
  inLibrary: "Added to the library", noTimeline: "Add clips to the timeline first.",
});
Object.assign(I18N.vi, {
  import: "Import", export: "Xuất file", media: "Thư viện", all: "Tất cả", videos: "Video", audios: "Âm thanh", imgs: "Ảnh",
  libEmpty: "Chưa có media.<br>Kéo thả file vào trang này, hoặc bấm <b>Import</b>.",
  analyzing: "đang phân tích", addClip: "Thêm vào timeline", addAudio: "Thêm làm track âm thanh", close: "Đóng",
  setIn: "[ Vào", setOut: "Ra ]", added: "Đã thêm vào {where}", whereClips: "track video", whereAudio: "một track âm thanh",
  dropHere: "Thả để import vào workspace",
  impTitle: "Import media", impPick: "Chọn file… (video, âm thanh, ảnh)", or: "hoặc",
  impPath: "Dùng file có sẵn trên máy (đường dẫn file hoặc thư mục, không chép lại)",
  impTr: "Nhận dạng giọng nói (để làm phụ đề)", lang: "Ngôn ngữ", auto: "Tự nhận diện", cancel: "Huỷ", impGo: "Import đường dẫn",
  impNote: "File tải lên được chép vào footage/ hoặc audio/ của workspace, rồi được phân tích (cảnh, độ lớn âm thanh, đoạn im lặng).",
  expTitle: "Xuất file", expVideo: "Video", expAudio: "Âm thanh", expSrt: "Phụ đề .srt", frameFmt: "Khung hình", quality: "Chất lượng",
  qHigh: "Cao", qStd: "Tiêu chuẩn", qSmall: "File nhẹ", asEdl: "Như trong EDL", afmt: "Định dạng", onlyRange: "Chỉ xuất một đoạn",
  from: "Từ (giây)", to: "Đến (giây)", expGo: "Xuất",
  expNote: "File được ghi vào renders/ trong workspace. Xuất âm thanh sẽ render bản mix đầy đủ trước.",
  jUpload: "Đang tải lên", jImport: "Import", jExport: "Xuất", download: "Tải về", reveal: "Hiện trong Finder",
  inLibrary: "Đã thêm vào thư viện", noTimeline: "Hãy thêm clip vào timeline trước.",
});

const E = { media: [], filter: "all", src: null, sIn: 0, sOut: 0, jobs: [], uploads: [], prevState: {} };
const ICON = { video: "▶", audio: "♪", image: "▣", unknown: "?" };

function toast(msg) {
  const t = el("div", "toast", msg);
  document.body.append(t);
  setTimeout(() => t.remove(), 2600);
}
function fsize(n) { return n > 1e9 ? (n / 1e9).toFixed(2) + " GB" : n > 1e6 ? (n / 1e6).toFixed(1) + " MB" : Math.round(n / 1e3) + " KB"; }

/* ---------- library ---------- */
const lib = $("#library");
lib.innerHTML = `<div class="lib-head"><h3></h3><button id="libImport" class="primary-ghost"></button></div>
  <div class="chips" id="chips"></div><div class="lib-list" id="libList"></div><div class="jobs" id="jobs"></div>`;
lib.querySelector("h3").textContent = T("media");
$("#libImport").textContent = "+ " + T("import");
$("#importBtn").textContent = T("import");
$("#exportBtn").textContent = T("export");

const FILTERS = [["all", "all"], ["video", "videos"], ["audio", "audios"], ["image", "imgs"]];
$("#chips").replaceChildren(...FILTERS.map(([k, label]) => {
  const b = el("button", null, T(label));
  b.dataset.f = k;
  b.onclick = () => { E.filter = k; renderLib(); };
  return b;
}));

async function loadMedia() {
  try { E.media = await getJSON("/api/media"); renderLib(); } catch {}
}

function renderLib() {
  document.querySelectorAll("#chips button").forEach((b) => b.classList.toggle("on", b.dataset.f === E.filter));
  const list = $("#libList");
  const items = E.media.filter((m) => E.filter === "all" || m.type === E.filter);
  if (!items.length) {
    const d = el("div", "lib-empty"); d.innerHTML = T("libEmpty");
    list.replaceChildren(d);
    return;
  }
  list.replaceChildren(...items.map((m) => {
    const it = el("div", "mitem" + (E.srcActive && E.src?.id === m.id ? " on" : ""));
    const th = el("div", "mthumb");
    if (m.type === "video" || m.type === "image") {
      const img = el("img"); img.loading = "lazy"; img.alt = "";
      img.src = `/api/thumb?src=${enc(m.id)}&t=${m.type === "video" ? Math.round((m.duration || 0) * 0.3 * 4) / 4 : 0}&h=80`;
      th.append(img);
    } else th.textContent = ICON[m.type] || "?";
    const info = el("div");
    info.style.minWidth = "0";
    info.append(el("div", "mname", m.id));
    const meta = [ICON[m.type] || "", m.duration ? fmt(m.duration) : "", m.width ? `${m.width}×${m.height}` : ""].filter(Boolean).join(" · ");
    const mm = el("div", "mmeta", meta);
    if (!m.analyzed) mm.append(" ", el("span", "spin"), " " + T("analyzing"));
    if (m.transcript) mm.append(" · T");
    info.append(mm);
    info.title = m.path;
    const add = el("button", "madd", "+");
    add.title = m.type === "audio" ? T("addAudio") : T("addClip");
    add.onclick = (e) => { e.stopPropagation(); addMedia(m, null, null, m.type === "audio" ? "audio" : "clip"); };
    const del = el("button", "madd mdel", "🗑");
    del.title = T("rmTitle");
    del.onclick = (e) => { e.stopPropagation(); askRemove(m); };
    const btns = el("div", "mbtns"); btns.append(add, del);
    it.append(th, info, btns);
    it.dataset.id = m.id;
    it.onclick = () => openSource(m);
    return it;
  }));
}

/* ---------- removing from the library ---------- */
Object.assign(I18N.en, {
  rmTitle: "Remove from library", rmUsed: "“{id}” is used in {edls}. Delete or replace those clips on the timeline first.",
  rmAsk: "Remove “{id}” from the library?", rmKeep: "Remove from library (keep the file)", rmTrash: "Remove and move the file to the Trash",
  rmOutside: "The file is outside the workspace ({path}); it is never deleted from here.", rmDone: "Removed {id}", rmTrashed: "Moved to the Trash: {path}",
});
Object.assign(I18N.vi, {
  rmTitle: "Gỡ khỏi thư viện", rmUsed: "“{id}” đang được dùng trong {edls}. Hãy xoá hoặc thay các clip đó trên timeline trước.",
  rmAsk: "Gỡ “{id}” khỏi thư viện?", rmKeep: "Gỡ khỏi thư viện (giữ file)", rmTrash: "Gỡ và chuyển file vào Thùng rác",
  rmOutside: "File nằm ngoài workspace ({path}); trang này không bao giờ xoá nó.", rmDone: "Đã gỡ {id}", rmTrashed: "Đã chuyển vào Thùng rác: {path}",
});
const rmDlg = el("dialog");
rmDlg.innerHTML = `<div class="dlg"><h2></h2><p class="note"></p><div class="acts rm-acts"></div></div>`;
document.body.append(rmDlg);
function askRemove(m) {
  const acts = rmDlg.querySelector(".rm-acts"), note = rmDlg.querySelector(".note");
  const btn = (txt, cls, fn) => { const b = el("button", cls, txt); b.type = "button"; b.onclick = fn; return b; };
  acts.replaceChildren();
  if (m.used_in?.length) {
    rmDlg.querySelector("h2").textContent = T("rmTitle");
    note.textContent = T("rmUsed", { id: m.id, edls: m.used_in.join(", ") });
    acts.append(btn("OK", "primary", () => rmDlg.close()));
  } else {
    rmDlg.querySelector("h2").textContent = T("rmAsk", { id: m.id });
    note.textContent = m.in_workspace ? m.path : T("rmOutside", { path: m.path });
    acts.append(btn(T("cancel"), "", () => rmDlg.close()), btn(T("rmKeep"), m.in_workspace ? "" : "primary", () => doRemove(m, false)));
    if (m.in_workspace) acts.append(btn(T("rmTrash"), "danger", () => doRemove(m, true)));
  }
  rmDlg.showModal();
}
async function doRemove(m, trash) {
  try {
    const r = await getJSON("/api/media/remove", { method: "POST", body: JSON.stringify({ id: m.id, trash_file: trash }) });
    rmDlg.close();
    if (E.src?.id === m.id) closeSource();
    toast(r.trashed ? T("rmTrashed", { path: r.trashed }) : T("rmDone", { id: m.id }));
    loadMedia();
  } catch (e) { toast(e.message); }
}

/* ---------- adding to the timeline ---------- */
async function addMedia(m, a, b, as) {
  const body = { edl: S.edl, src: m.id, as };
  if (a != null) body.in = a;
  if (b != null) body.out = b;
  if (as === "audio") { body.at = S.tl ? S.t : 0; if (m.type === "audio") body.volume = 0.5; }
  try {
    const r = await getJSON("/api/edl/append", { method: "POST", body: JSON.stringify(body) });
    toast(T("added", { where: T(as === "audio" ? "whereAudio" : "whereClips") }));
    if (!S.edl || !S.tl) { S.edl = r.edl; await bootTimeline(); } else await loadTimeline();
  } catch (e) { toast(e.message); }
}

/* ---------- source monitor ---------- */
const screen = $("#screen"), viewer = document.querySelector(".viewer");
const sv = el("div", "srcview");
sv.innerHTML = `<video id="srcVid" playsinline preload="auto"></video><img id="srcImg" alt=""><div class="audioicon">♪</div><div class="srclabel" id="srcLabel"></div>`;
screen.append(sv);
const bar = el("div", "srcbar");
bar.innerHTML = `<div class="scrub" id="scrub"><div class="inout"></div><div class="ph"></div></div>
  <div class="srcrow"><button id="sPlay">▶</button><div class="tc mono" id="sTc"></div>
  <button id="sIn"></button><button id="sOut"></button><span class="meta mono" id="sRange"></span>
  <div class="spacer"></div><button id="sAdd" class="primary"></button><button id="sAudio"></button>
  <button id="sClose">✕</button></div>`;
viewer.append(bar);
const sVid = $("#srcVid"), sImg = $("#srcImg");
$("#sIn").textContent = T("setIn"); $("#sOut").textContent = T("setOut");
$("#sAdd").textContent = T("addClip"); $("#sAudio").textContent = T("addAudio"); $("#sClose").title = T("close") + " (Esc)";

/* Two monitors, like an NLE: "Timeline" (program: preview render / live view) and "Source" (an
   imported file). Switching tabs keeps the source loaded; touching the timeline switches back. */
Object.assign(I18N.en, { tabTimeline: "Timeline", tabSource: "Source: {id}" });
Object.assign(I18N.vi, { tabTimeline: "Timeline", tabSource: "Nguồn: {id}" });
const monTabs = el("div", "montabs");
viewer.prepend(monTabs);
function renderMonTabs() {
  const tTl = el("button", E.srcActive ? "" : "on", "▦ " + T("tabTimeline"));
  tTl.onclick = showProgram;
  const tabs = [tTl];
  if (E.src) {
    const tSrc = el("button", E.srcActive ? "on" : "", (ICON[E.src.type] || "") + " " + T("tabSource", { id: E.src.id }));
    tSrc.onclick = showSource;
    const x = el("span", "x", "✕");
    x.title = T("close");
    x.onclick = (e) => { e.stopPropagation(); closeSource(); };
    tSrc.append(x);
    tabs.push(tSrc);
  }
  monTabs.replaceChildren(...tabs);
}
function setSrcActive(on) {
  E.srcActive = on;
  screen.classList.toggle("srcmode", on); viewer.classList.toggle("srcmode", on);
  if (!on) {
    sVid.pause();
    renderViewer(false);
    setTime(S.t, { force: true });   // re-sync the preview video / redraw the live view
  }
  renderMonTabs(); renderLib();
}
function showProgram() { if (E.srcActive) setSrcActive(false); }
function showSource() { if (E.src && !E.srcActive) { pause(); setSrcActive(true); } }
$("#scroll").addEventListener("pointerdown", showProgram, true);   // any timeline interaction
$("#edlSel").addEventListener("change", showProgram);
const _setView = setView;
setView = function (v) { showProgram(); _setView(v); };
renderMonTabs();

function openSource(m) {
  pause();
  E.src = m; E.sIn = 0; E.sOut = m.duration || 0;
  setSrcActive(true);
  $("#srcLabel").textContent = `${m.id}  ·  ${m.path}`;
  const isImg = m.type === "image";
  sImg.hidden = !isImg; sVid.hidden = isImg;
  sv.querySelector(".audioicon").hidden = m.type !== "audio";
  $("#scrub").style.visibility = isImg ? "hidden" : "";
  ["sPlay", "sIn", "sOut", "sRange"].forEach((id) => ($("#" + id).hidden = isImg));
  $("#sAdd").hidden = m.type === "audio";
  $("#sAudio").hidden = !(m.has_audio && m.type !== "image");
  if (isImg) { sImg.src = `/api/thumb?src=${enc(m.id)}&t=0&h=1080`; sVid.removeAttribute("src"); }
  else { sVid.src = `/media/source?src=${enc(m.id)}`; }
  renderLib(); updateSrc();
}
function closeSource() {
  sVid.pause(); sVid.removeAttribute("src"); sVid.load();
  E.src = null;
  setSrcActive(false);
}
const sDur = () => E.src?.duration || sVid.duration || 0;
const sFps = () => E.src?.fps || 30;
function updateSrc() {
  if (!E.src) return;
  const t = sVid.currentTime || 0, d = sDur();
  $("#sTc").innerHTML = `${fmt(t)} <small>/ ${fmt(d)}</small>`;
  $("#sRange").textContent = `${fmt(E.sIn)} → ${fmt(E.sOut)} (${(E.sOut - E.sIn).toFixed(2)}s)`;
  const sc = $("#scrub");
  if (d > 0) {
    sc.querySelector(".ph").style.left = (t / d) * 100 + "%";
    const io = sc.querySelector(".inout");
    io.style.left = (E.sIn / d) * 100 + "%"; io.style.width = (Math.max(0, E.sOut - E.sIn) / d) * 100 + "%";
  }
  $("#sPlay").textContent = sVid.paused ? "▶" : "❚❚";
}
sVid.addEventListener("timeupdate", updateSrc);
sVid.addEventListener("loadedmetadata", () => { if (E.src && !E.src.duration) E.sOut = sVid.duration; updateSrc(); });
sVid.addEventListener("play", () => { const loop = () => { updateSrc(); if (!sVid.paused) requestAnimationFrame(loop); }; loop(); });
sVid.addEventListener("pause", updateSrc);
const sSeek = (t) => { sVid.currentTime = Math.max(0, Math.min(sDur() - 0.001, t)); updateSrc(); };
const setIn = () => { E.sIn = sVid.currentTime; if (E.sOut <= E.sIn) E.sOut = sDur(); updateSrc(); };
const setOut = () => { E.sOut = sVid.currentTime; if (E.sOut <= E.sIn) E.sIn = 0; updateSrc(); };
$("#sPlay").onclick = () => (sVid.paused ? sVid.play() : sVid.pause());
$("#sIn").onclick = setIn; $("#sOut").onclick = setOut; $("#sClose").onclick = closeSource;
$("#sAdd").onclick = () => addMedia(E.src, E.src.type === "video" ? E.sIn : null, E.src.type === "video" ? E.sOut : null, "clip");
$("#sAudio").onclick = () => addMedia(E.src, E.sIn, E.sOut, "audio");
$("#scrub").addEventListener("pointerdown", (e) => {
  const sc = e.currentTarget, r = sc.getBoundingClientRect();
  const go = (ev) => sSeek(((ev.clientX - r.left) / r.width) * sDur());
  sc.setPointerCapture(e.pointerId); sVid.pause(); go(e);
  sc.addEventListener("pointermove", go);
  sc.addEventListener("pointerup", () => sc.removeEventListener("pointermove", go), { once: true });
});
document.addEventListener("keydown", (e) => {  // capture phase: wins over the timeline keys while the source monitor is open
  if (!E.srcActive || e.target.matches("input, select, textarea") || e.metaKey || e.ctrlKey || e.altKey || document.querySelector("dialog[open]")) return;
  const k = e.key, handled = () => { e.preventDefault(); e.stopPropagation(); };
  if (k === "Escape") { handled(); closeSource(); }
  else if (E.src.type === "image") { if (k === "Enter") { handled(); $("#sAdd").click(); } }
  else if (k === " ") { handled(); sVid.paused ? sVid.play() : sVid.pause(); }
  else if (k === "ArrowLeft") { handled(); sVid.pause(); sSeek(sVid.currentTime - (e.shiftKey ? 1 : 1 / sFps())); }
  else if (k === "ArrowRight") { handled(); sVid.pause(); sSeek(sVid.currentTime + (e.shiftKey ? 1 : 1 / sFps())); }
  else if (k === "i" || k === "I") { handled(); setIn(); }
  else if (k === "o" || k === "O") { handled(); setOut(); }
  else if (k === "Enter") { handled(); (E.src.type === "audio" ? $("#sAudio") : $("#sAdd")).click(); }
}, true);

/* ---------- import ---------- */
const impDlg = el("dialog");
impDlg.innerHTML = `<form method="dialog" class="dlg">
  <h2></h2>
  <div class="drop" id="impPick"><span></span><input type="file" id="impFiles" multiple hidden accept="video/*,audio/*,image/*,.mts,.mkv,.heic"></div>
  <div class="or"></div>
  <label id="impPathL"><span></span><input type="text" id="impPath" placeholder="/Users/…/Movies/trip"></label>
  <div class="row2"><label class="inline"><input type="checkbox" id="impTr"><span id="impTrL"></span></label>
  <label><span id="impLangL"></span><select id="impLang"><option value="auto"></option><option value="vi">Tiếng Việt</option><option value="en">English</option></select></label></div>
  <p class="note"></p>
  <div class="acts"><button value="cancel" id="impCancel"></button><button type="button" class="primary" id="impGo"></button></div>
</form>`;
document.body.append(impDlg);
impDlg.querySelector("h2").textContent = T("impTitle");
$("#impPick span").textContent = T("impPick");
impDlg.querySelector(".or").textContent = T("or");
$("#impPathL span").textContent = T("impPath");
$("#impTrL").textContent = T("impTr"); $("#impLangL").textContent = T("lang");
$("#impLang option").textContent = T("auto");
impDlg.querySelector(".note").textContent = T("impNote");
$("#impCancel").textContent = T("cancel"); $("#impGo").textContent = T("impGo");
const trLang = () => ($("#impTr").checked ? $("#impLang").value : null);

$("#impPick").onclick = () => $("#impFiles").click();
$("#impFiles").onchange = (e) => { [...e.target.files].forEach(upload); e.target.value = ""; impDlg.close(); };
$("#impGo").onclick = async () => {
  const path = $("#impPath").value.trim();
  if (!path) return $("#impPath").focus();
  try {
    await getJSON("/api/import-path", { method: "POST", body: JSON.stringify({ path, transcribe: trLang() }) });
    impDlg.close(); refreshJobs();
  } catch (e) { toast(e.message); }
};
$("#importBtn").onclick = $("#libImport").onclick = () => impDlg.showModal();

function upload(file) {
  const u = { id: "u" + Math.random().toString(36).slice(2), kind: "upload", label: file.name, state: "running", progress: 0, message: fsize(file.size) };
  E.uploads.push(u); renderJobs();
  const lang = trLang();
  const xhr = new XMLHttpRequest();
  xhr.open("POST", `/api/import?name=${enc(file.name)}` + (lang ? `&transcribe=${enc(lang)}` : ""));
  xhr.setRequestHeader("X-Reelsmith-Token", TOKEN);
  xhr.upload.onprogress = (e) => { if (e.lengthComputable) { u.progress = e.loaded / e.total; renderJobs(); } };
  const fail = (msg) => { u.state = "error"; u.message = msg; renderJobs(); };
  xhr.onload = () => {
    if (xhr.status >= 300) { let m = xhr.statusText; try { m = JSON.parse(xhr.responseText).error; } catch {} return fail(m); }
    E.uploads = E.uploads.filter((x) => x !== u);
    refreshJobs(); loadMedia();
  };
  xhr.onerror = () => fail("network error");
  xhr.send(file);
}

let dragDepth = 0;
const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
window.addEventListener("dragenter", (e) => { if (!hasFiles(e)) return; e.preventDefault(); dragDepth++; document.body.classList.add("dragging"); });
window.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
window.addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; document.body.classList.remove("dragging"); } });
window.addEventListener("drop", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault(); dragDepth = 0; document.body.classList.remove("dragging");
  [...e.dataTransfer.files].forEach(upload);
});
document.body.append(el("div", "dropzone", T("dropHere")));

/* ---------- export ---------- */
const expDlg = el("dialog");
expDlg.innerHTML = `<form method="dialog" class="dlg">
  <h2></h2>
  <div class="tabs" id="expTabs"><button type="button" data-k="video"></button><button type="button" data-k="audio"></button><button type="button" data-k="srt"></button></div>
  <div class="row2" id="expVideo"><label><span></span><select id="expFmt"></select></label>
    <label><span></span><select id="expQ"><option value="high"></option><option value="standard" selected></option><option value="small"></option></select></label></div>
  <div id="expAudio"><label><span></span><select id="expAf"><option>mp3</option><option>m4a</option><option>wav</option></select></label></div>
  <div id="expRangeBox"><label class="inline"><input type="checkbox" id="expRange"><span></span></label>
    <div class="row2" id="expRangeRow"><label><span></span><input type="number" id="expA" step="0.1" min="0"></label><label><span></span><input type="number" id="expB" step="0.1" min="0"></label></div></div>
  <p class="note"></p>
  <div class="acts"><button value="cancel" id="expCancel"></button><button type="button" class="primary" id="expGo"></button></div>
</form>`;
document.body.append(expDlg);
expDlg.querySelector("h2").textContent = T("expTitle");
const tabs = expDlg.querySelectorAll("#expTabs button");
["expVideo", "expAudio", "expSrt"].forEach((k, i) => (tabs[i].textContent = T(k)));
$("#expVideo label:first-child span").textContent = T("frameFmt");
$("#expVideo label:last-child span").textContent = T("quality");
["qHigh", "qStd", "qSmall"].forEach((k, i) => ($("#expQ").options[i].textContent = T(k)));
$("#expAudio span").textContent = T("afmt");
$("#expRangeBox label.inline span").textContent = T("onlyRange");
$("#expRangeRow label:first-child span").textContent = T("from");
$("#expRangeRow label:last-child span").textContent = T("to");
expDlg.querySelector(".note").textContent = T("expNote");
$("#expCancel").textContent = T("cancel"); $("#expGo").textContent = T("expGo");
const FORMATS = [["tiktok", "TikTok / Reels / Shorts · 9:16 · 1080×1920"], ["youtube", "YouTube · 16:9 · 1920×1080"],
  ["square", "1:1 · 1080×1080"], ["portrait", "4:5 · 1080×1350"], ["720p", "16:9 · 1280×720"], ["4k", "16:9 · 3840×2160"]];
let expKind = "video";
function syncExp() {
  tabs.forEach((b) => b.classList.toggle("on", b.dataset.k === expKind));
  $("#expVideo").hidden = expKind !== "video";
  $("#expAudio").hidden = expKind !== "audio";
  $("#expRangeBox").hidden = expKind === "srt";
  $("#expRangeRow").hidden = !$("#expRange").checked;
}
tabs.forEach((b) => (b.onclick = () => { expKind = b.dataset.k; syncExp(); }));
$("#expRange").onchange = syncExp;
$("#exportBtn").onclick = () => {
  if (!S.tl || !S.tl.clips?.length) return toast(T("noTimeline"));
  const o = S.tl.output;
  $("#expFmt").replaceChildren(...[["edl", `${T("asEdl")} · ${o.width}×${o.height}`], ...FORMATS].map(([v, l]) => { const op = el("option", null, l); op.value = v; return op; }));
  $("#expA").value = S.t.toFixed(1); $("#expB").value = dur().toFixed(1);
  syncExp(); expDlg.showModal();
};
$("#expGo").onclick = async () => {
  const body = { edl: S.edl, kind: expKind, format: $("#expFmt").value, quality: $("#expQ").value, audio_format: $("#expAf").value };
  if ($("#expRange").checked && expKind !== "srt") body.range = [+$("#expA").value, +$("#expB").value];
  try { await getJSON("/api/export", { method: "POST", body: JSON.stringify(body) }); expDlg.close(); refreshJobs(); }
  catch (e) { toast(e.message); }
};

/* ---------- jobs ---------- */
async function refreshJobs() {
  try {
    const jobs = await getJSON("/api/jobs");
    for (const j of jobs) {
      if (E.prevState[j.id] === "running" && j.state === "done" && j.kind === "import") loadMedia();
      E.prevState[j.id] = j.state;
    }
    E.jobs = jobs;
    renderJobs();
  } catch {}
}
function renderJobs() {
  const items = [...E.uploads, ...E.jobs];
  $("#jobs").replaceChildren(...items.slice(0, 12).map((j) => {
    const d = el("div", "job " + j.state);
    const top = el("div", "job-top");
    const kind = { upload: T("jUpload"), import: T("jImport"), export: T("jExport") }[j.kind] || j.kind;
    top.append(el("b", null, j.label),
      el("span", null, j.state === "running" ? (j.progress != null ? Math.round(j.progress * 100) + "%" : kind) : j.state === "done" ? "✓" : "✕"));
    d.append(top);
    const b = el("div", "bar" + (j.state === "running" && j.progress == null ? " indet" : ""));
    const i = el("i"); i.style.width = (j.state === "done" ? 1 : j.progress || 0) * 100 + "%";
    b.append(i); d.append(b);
    let msg = j.message || "";
    if (j.state === "done" && j.kind === "import") msg = T("inLibrary");
    if (j.state === "done" && j.result?.path) msg = `${j.result.path} · ${fsize(j.result.size)}`;
    if (msg) d.append(el("div", "job-msg", msg));
    if (j.state === "done" && j.kind === "export" && j.result?.path) {
      const acts = el("div", "job-actions");
      const dl = el("a", null, "⬇ " + T("download"));
      dl.href = `/api/download?path=${enc(j.result.path)}`; dl.download = "";
      const rv = el("a", null, T("reveal"));
      rv.onclick = () => getJSON("/api/reveal", { method: "POST", body: JSON.stringify({ path: j.result.path }) }).catch((e) => toast(e.message));
      acts.append(dl, rv); d.append(acts);
    }
    return d;
  }));
}

let tickN = 0;
setInterval(() => {
  tickN++;
  const busy = E.jobs.some((j) => j.state === "running") || E.uploads.some((u) => u.state === "running");
  if (busy || tickN % 4 === 0) refreshJobs();
  if (tickN % 5 === 0 || E.media.some((m) => !m.analyzed)) loadMedia();
}, 1000);
loadMedia(); refreshJobs();
