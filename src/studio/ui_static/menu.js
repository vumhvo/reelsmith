/* Reelsmith UI, part 4: right-click menus for library items, timeline blocks, empty timeline space
   and the viewer. Loaded last; uses the editing functions from edit.js and the library from editor.js. */
"use strict";

Object.assign(I18N.en, {
  mOpen: "Open in source viewer", mCopyPath: "Copy file path", mCopyId: "Copy media id", mCopied: "Copied",
  mSplitHere: "Split here", mSplitPh: "Split at playhead", mDuplicate: "Duplicate", mMute: "Mute clip audio", mUnmute: "Unmute clip audio",
  mAddTrans: "Add fade transition", mNoTrans: "Remove transition", mProps: "Properties", mShowSource: "Show in source viewer",
  mMoveHere: "Move start here", mToPlayhead: "Move start to playhead", mSeekHere: "Move playhead here", mTextHere: "Add text here",
  mSaveFrame: "Save this frame as PNG (all effects)", mFrameQueued: "Rendering the frame… see the jobs list", mCopyTc: "Copy timecode",
  mSelectClip: "Select this clip", play: "Play", pauseL: "Pause", mClose: "Close source viewer", mCopyText: "Copy text",
});
Object.assign(I18N.vi, {
  mOpen: "Mở trong màn xem nguồn", mCopyPath: "Sao chép đường dẫn file", mCopyId: "Sao chép media id", mCopied: "Đã sao chép",
  mSplitHere: "Cắt đôi tại đây", mSplitPh: "Cắt đôi tại playhead", mDuplicate: "Nhân bản", mMute: "Tắt tiếng clip", mUnmute: "Bật tiếng clip",
  mAddTrans: "Thêm chuyển cảnh mờ", mNoTrans: "Bỏ chuyển cảnh", mProps: "Thuộc tính", mShowSource: "Xem trong màn xem nguồn",
  mMoveHere: "Dời điểm bắt đầu tới đây", mToPlayhead: "Dời điểm bắt đầu tới playhead", mSeekHere: "Đưa playhead tới đây", mTextHere: "Thêm chữ tại đây",
  mSaveFrame: "Lưu frame này ra PNG (đủ hiệu ứng)", mFrameQueued: "Đang render frame… xem danh sách job", mCopyTc: "Sao chép timecode",
  mSelectClip: "Chọn clip này", play: "Phát", pauseL: "Dừng", mClose: "Đóng màn xem nguồn", mCopyText: "Sao chép nội dung",
});

/* ---------- the menu itself ---------- */
const menu = el("div", "ctxmenu");
menu.hidden = true;
menu.setAttribute("role", "menu");
document.body.append(menu);
const hideMenu = () => { menu.hidden = true; };

function showMenu(x, y, items) {
  menu.replaceChildren();
  for (const it of items) {
    if (!it) continue;
    if (it === "-") { if (menu.lastChild && !menu.lastChild.classList.contains("sep")) menu.append(el("div", "sep")); continue; }
    if (it.title) { menu.append(el("div", "mtitle", it.title)); continue; }
    const b = el("button", "mi" + (it.danger ? " danger" : ""));
    b.setAttribute("role", "menuitem");
    b.append(el("span", null, it.label), el("kbd", null, it.key || ""));
    b.disabled = !!it.disabled;
    b.onclick = () => { hideMenu(); it.fn(); };
    menu.append(b);
  }
  while (menu.lastChild?.classList.contains("sep")) menu.lastChild.remove();
  menu.hidden = false;
  const r = menu.getBoundingClientRect();
  menu.style.left = Math.max(4, Math.min(x, innerWidth - r.width - 4)) + "px";
  menu.style.top = Math.max(4, Math.min(y, innerHeight - r.height - 4)) + "px";
  menu.querySelector("button:not(:disabled)")?.focus({ preventScroll: true });
}
document.addEventListener("pointerdown", (e) => { if (!menu.hidden && !menu.contains(e.target)) hideMenu(); }, true);
window.addEventListener("blur", hideMenu);
window.addEventListener("resize", hideMenu);
document.addEventListener("scroll", (e) => { if (!menu.contains(e.target)) hideMenu(); }, true);
document.addEventListener("keydown", (e) => {  // capture: while the menu is open, keys drive the menu, not the timeline
  if (menu.hidden) return;
  if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); hideMenu(); }
  else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault(); e.stopPropagation();
    const bs = [...menu.querySelectorAll("button:not(:disabled)")], i = bs.indexOf(document.activeElement);
    bs[(i + (e.key === "ArrowDown" ? 1 : -1) + bs.length) % bs.length]?.focus();
  } else if (e.key !== "Enter" && e.key !== " ") { e.stopPropagation(); hideMenu(); }
}, true);

document.addEventListener("contextmenu", (e) => {
  if (e.target.closest("input, textarea, select, .ctxmenu, dialog")) return;  // keep native copy/paste in fields
  const items = menuFor(e);
  if (!items) return;
  e.preventDefault();
  showMenu(e.clientX, e.clientY, items);
});

/* ---------- actions shared by the menus ---------- */
const copyText = (s) => navigator.clipboard.writeText(s).then(() => toast(T("mCopied")), () => toast(s));
const reveal = (b) => getJSON("/api/reveal", { method: "POST", body: JSON.stringify(b) }).catch((e) => toast(e.message));
const timeAt = (e, lane) => Math.max(0, (e.clientX - lane.getBoundingClientRect().left) / S.pps);
const inside = (c, t) => !!c && t > c.start + 1e-3 && t < c.end - 1e-3;

function selectBlock(type, index) {
  S.selected = { type, index };
  renderInspector();
  document.querySelectorAll(".blk.sel").forEach((x) => x.classList.remove("sel"));
  document.querySelectorAll(`.blk[data-sel="${type}:${index}"]`).forEach((x) => x.classList.add("sel"));
}
function focusInspector() {
  const box = $("#inspector");
  box.scrollTop = 0;
  box.querySelector("input:not([type=range]), textarea, select")?.focus();
}
function duplicate(type, index) {
  const it = type === "clip" ? null : (S.tl[LISTS[type]] || []).find((x) => x.index === index);
  commit((doc) => {
    const list = doc[LISTS[type]], e = JSON.parse(JSON.stringify(list[index]));
    if (type === "clip") delete e.transition;
    else if (type === "audio") e.at = r3(it.end);
    else { e.start = r3(it.end); if (e.end != null) e.end = r3(it.end + (it.end - it.start)); }
    list.splice(index + 1, 0, e);
  }, () => selectBlock(type, index + 1));
}
function moveStart(type, index, t) {
  const it = (S.tl[LISTS[type]] || []).find((x) => x.index === index);
  t = r3(snap(Math.max(0, t)));
  commit((doc) => {
    const e = doc[LISTS[type]][index];
    if (type === "audio") { e.at = t; return; }
    e.start = t;
    if (e.end != null) e.end = r3(t + (it.end - it.start));
  });
}
function showInSource(c, m) {
  openSource(m);
  if (c.kind !== "video") return;
  sVid.addEventListener("loadedmetadata", () => { E.sIn = c.in; E.sOut = c.out; sVid.currentTime = c.in; updateSrc(); }, { once: true });
}
function saveFrame() {
  getJSON("/api/export", { method: "POST", body: JSON.stringify({ edl: S.edl, kind: "frame", t: S.t }) })
    .then(() => { toast(T("mFrameQueued")); refreshJobs(); }, (e) => toast(e.message));
}

/* ---------- which menu for what ---------- */
function menuFor(e) {
  const mi = e.target.closest(".mitem");
  if (mi) { const m = E.media.find((x) => x.id === mi.dataset.id); return m && mediaMenu(m); }
  const blk = e.target.closest(".blk[data-sel]");
  if (blk) { const [type, i] = blk.dataset.sel.split(":"); return blockMenu(type, +i, timeAt(e, blk.closest(".lane"))); }
  const lane = e.target.closest(".tl-inner .lane");
  if (lane) return laneMenu(timeAt(e, lane));
  if (e.target.closest("#screen")) return E.srcActive ? sourceMenu() : viewerMenu();
  if (e.target.closest(".tl-scroll")) return laneMenu(S.t);
  return null;
}

function mediaMenu(m) {
  return [
    { title: `${m.id} · ${m.path}` },
    { label: T("mOpen"), fn: () => openSource(m) },
    m.type !== "audio" && { label: T("addClip"), fn: () => addMedia(m, null, null, "clip") },
    m.has_audio && m.type !== "image" && { label: T("addAudio"), fn: () => addMedia(m, null, null, "audio") },
    "-",
    { label: T("reveal"), fn: () => reveal({ id: m.id }) },
    { label: T("mCopyPath"), fn: () => copyText(m.path) },
    { label: T("mCopyId"), fn: () => copyText(m.id) },
    "-",
    { label: T("rmTitle") + "…", danger: true, fn: () => askRemove(m) },
  ];
}

function blockMenu(type, index, t) {
  if (!S.tl) return null;
  if (type === "captions") {
    const c = S.tl.captions[index];
    return c && [{ title: c.text }, { label: T("mSeekHere"), fn: () => setTime(c.start) }, { label: T("mCopyText"), fn: () => copyText(c.text) }];
  }
  selectBlock(type, index);
  if (type === "clip") {
    const c = S.tl.clips.find((x) => x.index === index);
    if (!c) return null;
    const m = E.media.find((x) => x.id === c.src), ph = inside(c, S.t);
    return [
      { title: `#${c.index} ${c.label} · ${fmt(c.start)} → ${fmt(c.end)}` },
      { label: T("mSplitHere"), disabled: !inside(c, t), fn: () => { setTime(t); splitAt(t); } },
      { label: T("mSplitPh"), key: "B", disabled: !ph, fn: () => splitAt() },
      { label: T("trimStart"), key: "Q", disabled: !ph, fn: () => trimToPlayhead("start") },
      { label: T("trimEnd"), key: "W", disabled: !ph, fn: () => trimToPlayhead("end") },
      "-",
      c.kind !== "color" && { label: T("crop") + "…", fn: () => enterCrop(c.index) },
      { label: T("mDuplicate"), fn: () => duplicate("clip", c.index) },
      c.has_audio && { label: c.mute ? T("mUnmute") : T("mMute"), fn: () => commit((doc) => setPath(doc.clips[c.index], "mute", c.mute ? "" : true)) },
      c.index > 0 && { label: c.entry.transition ? T("mNoTrans") : T("mAddTrans"),
        fn: () => commit((doc) => { const x = doc.clips[c.index]; if (x.transition) delete x.transition; else x.transition = { type: "fade", duration: 0.5 }; }) },
      { label: T("mProps"), fn: focusInspector },
      "-",
      m && { label: T("mShowSource"), fn: () => showInSource(c, m) },
      c.src && { label: T("reveal"), fn: () => reveal({ id: c.src }) },
      "-",
      { label: T("del"), key: "Del", danger: true, fn: deleteSelected },
    ];
  }
  const it = (S.tl[LISTS[type]] || []).find((x) => x.index === index);
  if (!it) return null;
  return [
    { title: `${{ text: T("text"), images: T("images"), audio: T("audio") }[type]} · ${it.label}` },
    { label: T("mMoveHere"), fn: () => moveStart(type, index, t) },
    { label: T("mToPlayhead"), fn: () => moveStart(type, index, S.t) },
    { label: T("mDuplicate"), fn: () => duplicate(type, index) },
    { label: T("mProps"), fn: focusInspector },
    type === "audio" && it.src && { label: T("reveal"), fn: () => reveal({ id: it.src }) },
    "-",
    { label: T("del"), key: "Del", danger: true, fn: deleteSelected },
  ];
}

function laneMenu(t) {
  const c = S.tl && clipUnder(t);
  return [
    { title: `${fmt(t)} · ${T("frame")} ${Math.floor(t * fps() + 1e-6)}` },
    { label: T("mSeekHere"), fn: () => setTime(t) },
    { label: T("mSplitHere"), disabled: !inside(c, t), fn: () => { setTime(t); splitAt(t); } },
    { label: T("mTextHere"), disabled: !S.tl, fn: () => { setTime(t); addText(); } },
    "-",
    { label: T("undo"), key: "⌘Z", disabled: !H.undo.length, fn: undo },
    { label: T("redo"), key: "⇧⌘Z", disabled: !H.redo.length, fn: redo },
    { label: T("fit"), fn: () => $("#fitBtn").click() },
  ];
}

function viewerMenu() {
  if (!S.tl) return null;
  const c = clipUnder(S.t), hasPreview = S.view === "preview" && !!S.ver?.preview_mtime;
  return [
    { title: `${fmt(S.t)} · ${T("frame")} ${Math.floor(S.t * fps() + 1e-6)}` },
    hasPreview && { label: S.playing ? T("pauseL") : T("play"), key: "Space", fn: () => (S.playing ? pause() : play()) },
    { label: T("mSaveFrame"), disabled: !!S.tl.errors?.length, fn: saveFrame },
    { label: T("mCopyTc"), fn: () => copyText(fmt(S.t)) },
    "-",
    c && { label: T("mSelectClip"), fn: () => selectBlock("clip", c.index) },
    c && c.kind !== "color" && { label: T("crop") + "…", fn: () => enterCrop(c.index) },
    { label: T("mSplitPh"), key: "B", disabled: !inside(c, S.t), fn: () => splitAt() },
    "-",
    { label: S.view === "preview" ? T("live") : T("preview"), key: "S", fn: () => setView(S.view === "preview" ? "source" : "preview") },
  ];
}

function sourceMenu() {
  const m = E.src, timed = m.type !== "image";
  return [
    { title: m.id },
    timed && { label: T("setIn"), key: "I", fn: setIn },
    timed && { label: T("setOut"), key: "O", fn: setOut },
    m.type !== "audio" && { label: T("addClip"), key: "Enter", fn: () => $("#sAdd").click() },
    m.has_audio && m.type !== "image" && { label: T("addAudio"), fn: () => $("#sAudio").click() },
    "-",
    { label: T("reveal"), fn: () => reveal({ id: m.id }) },
    { label: T("mClose"), key: "Esc", fn: closeSource },
  ];
}
