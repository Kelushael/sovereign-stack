#!/usr/bin/env python3
"""
sov --ui  ·  SOVEREIGN AGENT ACTIVITY WINDOW
═══════════════════════════════════════════════════════════════════════
Live play-by-play PiP window showing the agent operating in real-time.

THREE MODES  (agent switches automatically or user clicks tab)
──────────────────────────────────────────────────────────────
  TERMINAL   agent types commands char-by-char in a live terminal
             sandboxed subprocess → real output streams in
             "practice run" before hitting real shell

  WEB        agent navigates URLs, page loads into iframe
             agent scrolls, clicks, types in real web pages

  UI         agent operates the HTML/JS it just built
             virtual cursor + keyboard show every interaction
             screenshot fed back so agent sees what it broke

UNIFIED ACTIVITY FEED  (right panel)
──────────────────────────────────────────────────────────────
  scrolling log of every agent action across all three modes
  colour-coded: green=terminal  cyan=web  pink=ui

KEYBOARD PiP  (floating, appears on any keypress)
  QWERTY overlay highlights each key as agent types it
  shows current typed buffer

Port 7071
  GET  /              → activity window HTML
  GET  /activity      → SSE: all agent activity events
  GET  /screenshot    → latest screenshot {b64, ts, mode, label}
  GET  /domstate      → last interaction result
  POST /push          → {mode, action, ...payload}  (all event types)
  POST /feedback      → browser → {b64, mode, label, hit_element}
"""
import sys, os, json, threading, time, queue, subprocess, shlex
import http.server, socketserver, webbrowser
from urllib.parse import urlparse
from pathlib import Path

PINK = "\033[38;2;255;105;180m"
CYAN = "\033[38;2;0;220;255m"
LIME = "\033[38;2;57;255;100m"
GRAY = "\033[38;2;85;85;105m"
RST  = "\033[0m"
BOLD = "\033[1m"

PORT        = 7071
SANDBOX_DIR = Path.home() / ".sov" / "sandbox"
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

# ── shared state ──────────────────────────────────────────────────────────────
_last_screenshot = {"b64": None, "ts": None, "mode": None, "label": ""}
_activity_clients: list = []   # SSE browsers
_lock = threading.Lock()

# keyboard rows for PiP
_KB = json.dumps([
    ["Esc","1","2","3","4","5","6","7","8","9","0","-","=","⌫"],
    ["Tab","q","w","e","r","t","y","u","i","o","p","[","]","\\"],
    ["Cap","a","s","d","f","g","h","j","k","l",";","'","Enter"],
    ["Shift","z","x","c","v","b","n","m",",",".","/","Shift"],
    ["Ctrl","Alt","Space","Alt","Ctrl"],
])

# ── HTML ──────────────────────────────────────────────────────────────────────
_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>SOV · AGENT ACTIVITY</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --dark:#010810;--darker:#000508;
  --cyan:#00e5ff;--pink:#ff69b4;--green:#00ff9d;--gold:#ffd700;
  --border:rgba(0,229,255,0.15);
  --term-bg:#0a0f0a;--web-bg:#f5f5f5;--ui-bg:#010810;
}
html,body{background:var(--dark);color:#e0f4ff;
  font-family:'Courier New',monospace;height:100vh;overflow:hidden}

/* ── layout ── */
#root{display:grid;grid-template-rows:auto 1fr auto;height:100vh}

/* ── titlebar ── */
#titlebar{
  display:flex;align-items:center;justify-content:space-between;
  padding:.28rem 1rem;background:rgba(0,4,12,0.98);
  border-bottom:1px solid var(--border);font-size:.55rem;letter-spacing:.1em;
}
.pulse-dot{width:6px;height:6px;border-radius:50%;background:#ff69b4;
  box-shadow:0 0 6px #ff69b4;display:inline-block;margin-right:.4rem;
  animation:pulse 1.8s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:.35}50%{opacity:1}}

/* ── mode tabs ── */
#tabs{display:flex;gap:.15rem;align-items:center}
.tab{
  padding:.22rem .7rem;border-radius:4px;font-size:.52rem;letter-spacing:.1em;
  cursor:pointer;border:1px solid transparent;transition:all .15s;color:#3a4a5a;
}
.tab.term{border-color:rgba(0,255,157,.18);color:#1a3a2a}
.tab.term:hover,.tab.term.active{background:rgba(0,255,157,.12);color:#00ff9d;border-color:#00ff9d;box-shadow:0 0 8px rgba(0,255,157,.2)}
.tab.web {border-color:rgba(0,229,255,.18);color:#1a2a3a}
.tab.web:hover,.tab.web.active {background:rgba(0,229,255,.12);color:#00e5ff;border-color:#00e5ff;box-shadow:0 0 8px rgba(0,229,255,.2)}
.tab.ui  {border-color:rgba(255,105,180,.18);color:#3a1a2a}
.tab.ui:hover,.tab.ui.active  {background:rgba(255,105,180,.12);color:#ff69b4;border-color:#ff69b4;box-shadow:0 0 8px rgba(255,105,180,.2)}

/* ── main area: stage + feed ── */
#main{display:grid;grid-template-columns:1fr 220px;overflow:hidden;min-height:0}

/* ── stage (left) ── */
#stage{position:relative;overflow:hidden;background:var(--dark)}

/* panels */
.panel{position:absolute;inset:0;display:none;flex-direction:column}
.panel.active{display:flex}

/* TERMINAL panel */
#term-panel{background:var(--term-bg)}
#term-screen{
  flex:1;overflow-y:auto;padding:.6rem .8rem;
  font-size:.72rem;line-height:1.55;
  color:#c8ffc8;word-break:break-all;
}
#term-screen::-webkit-scrollbar{width:3px}
#term-screen::-webkit-scrollbar-thumb{background:rgba(0,255,157,.2)}
#term-input-row{
  display:flex;align-items:center;gap:.4rem;padding:.3rem .8rem;
  border-top:1px solid rgba(0,255,157,.1);flex-shrink:0;
  background:rgba(0,6,0,.6);
}
#term-prompt{color:#00ff9d;font-size:.7rem;white-space:nowrap}
#term-input{
  flex:1;background:transparent;border:none;outline:none;
  color:#c8ffc8;font-family:'Courier New',monospace;font-size:.7rem;caret-color:#00ff9d;
}

/* WEB panel */
#web-panel{background:#fff}
#url-bar{
  display:flex;align-items:center;gap:.5rem;padding:.25rem .6rem;
  background:#1a1a2e;border-bottom:1px solid #2a2a4e;flex-shrink:0;
}
#url-spinner{font-size:.65rem;color:#4a4a7a;width:14px;text-align:center}
#url-display{
  flex:1;font-size:.58rem;color:#7a9abf;letter-spacing:.03em;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}
#web-frame{flex:1;border:none;width:100%}

/* UI panel */
#ui-panel{background:var(--ui-bg)}
#ui-frame{flex:1;border:none;width:100%;background:#fff}
#vcursor{
  position:absolute;pointer-events:none;z-index:99;
  transform:translate(-50%,-50%);display:none;
  transition:left .1s ease,top .1s ease;
}
#vcursor svg{filter:drop-shadow(0 0 4px #ff69b4) drop-shadow(0 0 9px rgba(255,105,180,.5))}
#vring{
  position:absolute;width:28px;height:28px;border-radius:50%;
  border:2px solid #ff69b4;pointer-events:none;z-index:98;
  transform:translate(-50%,-50%);opacity:0;
}
@keyframes ripple{0%{transform:translate(-50%,-50%) scale(.2);opacity:1}100%{transform:translate(-50%,-50%) scale(2);opacity:0}}
#vring.fire{animation:ripple .38s ease-out forwards}
#coord{
  position:absolute;top:4px;left:4px;z-index:100;
  background:rgba(0,0,0,.75);border:1px solid rgba(255,105,180,.3);
  border-radius:4px;padding:.08rem .3rem;font-size:.43rem;color:#ff69b4;
  display:none;pointer-events:none;
}

/* ── activity feed (right) ── */
#feed{
  border-left:1px solid var(--border);overflow-y:auto;
  background:rgba(0,2,8,.6);display:flex;flex-direction:column;
}
#feed-title{
  padding:.3rem .6rem;font-size:.48rem;letter-spacing:.12em;color:#2a3a4a;
  border-bottom:1px solid var(--border);flex-shrink:0;
  background:rgba(0,4,12,.9);
}
#feed-list{flex:1;overflow-y:auto;padding:.3rem}
#feed-list::-webkit-scrollbar{width:2px}
#feed-list::-webkit-scrollbar-thumb{background:rgba(0,229,255,.15)}
.feed-item{
  font-size:.45rem;line-height:1.5;padding:.15rem .3rem;
  border-radius:3px;margin-bottom:.12rem;
  border-left:2px solid transparent;
}
.feed-item.term{border-color:#00ff9d;color:#4a7a4a}
.feed-item.web {border-color:#00e5ff;color:#2a5a7a}
.feed-item.ui  {border-color:#ff69b4;color:#7a2a4a}
.feed-item .fi-time{color:#2a3a4a;margin-right:.3rem}
.feed-item .fi-mode{font-weight:700;margin-right:.3rem}

/* ── keyboard PiP ── */
#kbd{
  position:absolute;bottom:2.5rem;right:230px;z-index:200;
  background:rgba(0,4,12,.94);border:1px solid rgba(0,229,255,.12);
  border-radius:7px;padding:.35rem .45rem;backdrop-filter:blur(14px);
  box-shadow:0 0 20px rgba(0,0,0,.7);
  display:none;flex-direction:column;gap:.12rem;
}
#kbd.show{display:flex}
#kbd-hdr{font-size:.42rem;color:var(--cyan);letter-spacing:.1em;margin-bottom:.08rem;
  display:flex;justify-content:space-between;align-items:center}
#kbd-buf{color:#ff69b4;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kr{display:flex;gap:.1rem;justify-content:center}
.kk{
  background:rgba(0,229,255,.06);border:1px solid rgba(0,229,255,.1);
  border-radius:2px;padding:.08rem .18rem;color:#3a5a6a;
  font-family:inherit;font-size:.4rem;white-space:nowrap;
  transition:all .1s;
}
.kk.lit{background:rgba(255,105,180,.28);border-color:#ff69b4;color:#fff;
  box-shadow:0 0 5px rgba(255,105,180,.4)}
.w2{padding:.08rem .45rem}.w3{padding:.08rem .9rem}.w5{padding:.08rem 1.7rem}

/* ── statusbar ── */
#statusbar{
  display:flex;align-items:center;justify-content:space-between;
  padding:.2rem 1rem;border-top:1px solid var(--border);
  font-size:.46rem;color:#2a3a4a;letter-spacing:.05em;flex-shrink:0;
  background:rgba(0,4,12,.95);
}
#status-action{max-width:50%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#fb-row{display:flex;align-items:center;gap:.35rem}
#fb-dot{width:5px;height:5px;border-radius:50%;background:#00ff9d;
  box-shadow:0 0 4px #00ff9d;opacity:0;transition:opacity .25s}
#fb-dot.on{opacity:1}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"
        crossorigin="anonymous"></script>
</head>
<body>
<div id="root">

<!-- titlebar -->
<div id="titlebar">
  <span><span class="pulse-dot"></span>SOV · AGENT ACTIVITY  <span id="mode-badge" style="color:#2a3a4a">—</span></span>
  <div id="tabs">
    <div class="tab term active" onclick="switchMode('terminal')">⬛ TERMINAL</div>
    <div class="tab web"  onclick="switchMode('web')">🌐 WEB</div>
    <div class="tab ui"   onclick="switchMode('ui')">🖥 UI</div>
  </div>
  <span id="ts" style="color:#2a3a4a;font-size:.48rem">—</span>
</div>

<!-- main -->
<div id="main">
  <div id="stage">

    <!-- TERMINAL panel -->
    <div id="term-panel" class="panel active">
      <div id="term-screen"><span style="color:#2a4a2a">─ sov terminal sandbox ─ safe mode ─</span><br></div>
      <div id="term-input-row">
        <span id="term-prompt">amallo@sov:~$&nbsp;</span>
        <input id="term-input" readonly spellcheck="false" autocomplete="off">
      </div>
    </div>

    <!-- WEB panel -->
    <div id="web-panel" class="panel">
      <div id="url-bar">
        <span id="url-spinner">○</span>
        <span id="url-display">about:blank</span>
      </div>
      <iframe id="web-frame" src="about:blank"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups"></iframe>
    </div>

    <!-- UI panel -->
    <div id="ui-panel" class="panel">
      <iframe id="ui-frame" srcdoc=""
              sandbox="allow-scripts allow-same-origin allow-forms allow-modals"></iframe>
      <div id="vcursor">
        <svg width="18" height="18" viewBox="0 0 18 18">
          <polygon points="2,1 2,14 6,10 9,16 11,15 8,9 13,9"
                   fill="#ff69b4" stroke="rgba(255,255,255,.6)" stroke-width=".5"/>
        </svg>
      </div>
      <div id="vring"></div>
      <div id="coord">0 , 0</div>
    </div>

    <!-- keyboard PiP (floats over stage) -->
    <div id="kbd">
      <div id="kbd-hdr"><span>⌨ AGENT INPUT</span><span id="kbd-buf"></span></div>
      <div id="kbd-rows"></div>
    </div>

  </div><!-- /stage -->

  <!-- activity feed -->
  <div id="feed">
    <div id="feed-title">▸ ACTIVITY FEED</div>
    <div id="feed-list"></div>
  </div>

</div><!-- /main -->

<!-- statusbar -->
<div id="statusbar">
  <span id="status-action">waiting for agent…</span>
  <span id="fb-row"><span id="fb-dot"></span><span id="fb-label">no feedback</span></span>
</div>

</div><!-- /root -->

<script>
// ═══════════════════════════════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════════════════════════════
const KB = """ + _KB + r""";
const WIDE = {Tab:2,Cap:2,Enter:2,Shift:2,Ctrl:2,Alt:2,Esc:2,'⌫':2,Space:5};
const keyEls = {};

// build keyboard PiP
KB.forEach(row => {
  const rd = document.createElement('div');
  rd.className = 'kr';
  row.forEach(k => {
    const el = document.createElement('span');
    el.className = 'kk' + (WIDE[k] ? ` w${WIDE[k]}` : '');
    el.textContent = k;
    keyEls[k.toLowerCase()] = el;
    if(k==='Space') keyEls[' '] = el;
    if(k==='⌫') keyEls['backspace'] = el;
    rd.appendChild(el);
  });
  document.getElementById('kbd-rows').appendChild(rd);
});

let currentMode = 'terminal';
let kbdBuf = '';

// ═══════════════════════════════════════════════════════════════════
//  MODE SWITCHING
// ═══════════════════════════════════════════════════════════════════
function switchMode(m) {
  currentMode = m;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelector('.tab.'+({terminal:'term',web:'web',ui:'ui'}[m]||m))
          .classList.add('active');
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById({terminal:'term-panel',web:'web-panel',ui:'ui-panel'}[m])
          .classList.add('active');
  document.getElementById('mode-badge').textContent = m.toUpperCase();
  document.getElementById('mode-badge').style.color =
    {terminal:'#00ff9d',web:'#00e5ff',ui:'#ff69b4'}[m];
}

// ═══════════════════════════════════════════════════════════════════
//  SSE — unified activity stream
// ═══════════════════════════════════════════════════════════════════
const es = new EventSource('/activity');
es.onmessage = e => {
  const ev = JSON.parse(e.data);
  dispatch(ev);
};
es.onerror = () => {
  log('system','sys','stream error — retrying…');
};

// ═══════════════════════════════════════════════════════════════════
//  DISPATCH
// ═══════════════════════════════════════════════════════════════════
function dispatch(ev) {
  const {mode, action} = ev;
  document.getElementById('ts').textContent = new Date().toLocaleTimeString();
  document.getElementById('status-action').textContent =
    `[${mode||'sys'}] ${action||''} ${ev.text||ev.url||ev.html?'…':ev.cmd||''}`;

  log(mode||'sys', action, ev);

  if(mode === 'terminal') handleTerminal(ev);
  else if(mode === 'web')  handleWeb(ev);
  else if(mode === 'ui')   handleUI(ev);
}

// ═══════════════════════════════════════════════════════════════════
//  TERMINAL  mode handlers
// ═══════════════════════════════════════════════════════════════════
const screen = document.getElementById('term-screen');
const inputEl = document.getElementById('term-input');
let termBuf = '';

function termPrint(html) {
  screen.insertAdjacentHTML('beforeend', html);
  screen.scrollTop = screen.scrollHeight;
}

function handleTerminal(ev) {
  switchMode('terminal');
  switch(ev.action) {

    case 'type': {
      // agent is typing a command char by char
      showKbd(true);
      const chars = [...(ev.text||'')];
      let i = 0;
      termBuf = '';
      inputEl.value = '';
      function nextChar() {
        if(i >= chars.length) {
          setTimeout(() => capture('terminal', `typed: ${ev.text}`), 300);
          return;
        }
        const ch = chars[i++];
        termBuf += ch;
        inputEl.value = termBuf;
        litKey(ch);
        setTimeout(nextChar, 50 + Math.random()*40);
      }
      nextChar();
      break;
    }

    case 'exec': {
      // command fires — show in terminal as entered line
      const cmd = ev.cmd || termBuf;
      termPrint(`<span style="color:#00ff9d">amallo@sov:~$</span> <span style="color:#e0f4ff">${esc(cmd)}</span>\n`);
      inputEl.value = '';
      termBuf = '';
      showKbd(false);
      break;
    }

    case 'output': {
      // stdout/stderr streaming in
      const col = ev.stderr ? '#ff6b6b' : '#a8d8a8';
      termPrint(`<span style="color:${col}">${esc(ev.text||'')}</span>`);
      setTimeout(() => capture('terminal', 'output'), 200);
      break;
    }

    case 'output_done': {
      termPrint(`\n`);
      capture('terminal', 'exec complete');
      break;
    }

    case 'clear':
      screen.innerHTML = '<span style="color:#2a4a2a">─ cleared ─</span><br>';
      break;
  }
}

// ═══════════════════════════════════════════════════════════════════
//  WEB  mode handlers
// ═══════════════════════════════════════════════════════════════════
const webFrame  = document.getElementById('web-frame');
const urlDisp   = document.getElementById('url-display');
const urlSpin   = document.getElementById('url-spinner');

function handleWeb(ev) {
  switchMode('web');
  switch(ev.action) {

    case 'navigate': {
      urlDisp.textContent = ev.url;
      urlSpin.textContent = '◌';
      urlSpin.style.animation = 'pulse 1s linear infinite';
      webFrame.src = ev.url;
      webFrame.onload = () => {
        urlSpin.textContent = '●';
        urlSpin.style.color = '#00ff9d';
        urlSpin.style.animation = '';
        setTimeout(() => capture('web', `loaded: ${ev.url}`), 600);
      };
      break;
    }

    case 'scroll': {
      try { webFrame.contentWindow.scrollBy(0, ev.dy||200); } catch(e){}
      setTimeout(() => capture('web', `scroll dy=${ev.dy||200}`), 300);
      break;
    }

    case 'click': {
      showKbd(false);
      try {
        const doc = webFrame.contentDocument;
        const el = doc && doc.elementFromPoint(ev.x, ev.y);
        if(el) {
          el.dispatchEvent(new MouseEvent('click',
            {bubbles:true,cancelable:true,clientX:ev.x,clientY:ev.y,
             view:webFrame.contentWindow}));
        }
      } catch(e) {}
      setTimeout(() => capture('web', `click ${ev.x},${ev.y}`), 500);
      break;
    }

    case 'type': {
      showKbd(true);
      const chars = [...(ev.text||'')];
      let i = 0;
      kbdBuf = '';
      function nextWeb() {
        if(i >= chars.length) {
          setTimeout(() => capture('web',`typed: ${ev.text}`), 400);
          return;
        }
        const ch = chars[i++];
        kbdBuf += ch;
        document.getElementById('kbd-buf').textContent = kbdBuf;
        litKey(ch);
        try {
          const doc = webFrame.contentDocument;
          const el = doc && (doc.elementFromPoint(ev.x||0, ev.y||0) || doc.activeElement);
          if(el && (el.tagName==='INPUT'||el.tagName==='TEXTAREA')) {
            el.value = ev.text.slice(0, i);
            el.dispatchEvent(new Event('input',{bubbles:true}));
          }
        } catch(e) {}
        setTimeout(nextWeb, 55 + Math.random()*35);
      }
      nextWeb();
      break;
    }

    case 'load_html': {
      // direct HTML load into web panel (like a fetched page)
      const blob = new Blob([ev.html||''], {type:'text/html'});
      webFrame.src = URL.createObjectURL(blob);
      setTimeout(() => capture('web','html loaded'), 500);
      break;
    }
  }
}

// ═══════════════════════════════════════════════════════════════════
//  UI  mode handlers
// ═══════════════════════════════════════════════════════════════════
const uiFrame  = document.getElementById('ui-frame');
const vcursor  = document.getElementById('vcursor');
const vring    = document.getElementById('vring');
const coordEl  = document.getElementById('coord');

function handleUI(ev) {
  switchMode('ui');
  switch(ev.action) {

    case 'push_html': {
      uiFrame.srcdoc = ev.html || '';
      setTimeout(() => capture('ui', ev.label||'ui render'), 900);
      break;
    }

    case 'move': {
      moveCursor(ev.x, ev.y);
      break;
    }

    case 'click':
    case 'dblclick': {
      showKbd(false);
      moveCursor(ev.x, ev.y);
      setTimeout(() => {
        ripple(ev.x, ev.y);
        injectClick(ev.x, ev.y, ev.action);
        setTimeout(() => capture('ui', `${ev.action} @ ${ev.x},${ev.y}`), 500);
      }, 180);
      break;
    }

    case 'type': {
      showKbd(true);
      const chars = [...(ev.text||'')];
      let i = 0;
      kbdBuf = '';
      function nextUI() {
        if(i >= chars.length) {
          setTimeout(() => capture('ui',`typed: ${ev.text}`), 400);
          showKbd(false);
          return;
        }
        const ch = chars[i++];
        kbdBuf += ch;
        document.getElementById('kbd-buf').textContent = kbdBuf;
        litKey(ch);
        injectKey(ch);
        injectInputValue(ev.x||0, ev.y||0, ev.text.slice(0,i));
        setTimeout(nextUI, 55 + Math.random()*40);
      }
      nextUI();
      break;
    }

    case 'key': {
      showKbd(true);
      litKey(ev.key, 350);
      injectKey(ev.key, true);
      setTimeout(() => capture('ui', `key: ${ev.key}`), 500);
      break;
    }

    case 'scroll': {
      try {
        const doc = uiFrame.contentDocument;
        const el = doc && (doc.querySelector(ev.selector) || doc.documentElement);
        if(el) el.scrollTop += (ev.dy||120);
      } catch(e) {}
      setTimeout(() => capture('ui', `scroll`), 300);
      break;
    }
  }
}

// ═══════════════════════════════════════════════════════════════════
//  VIRTUAL CURSOR helpers
// ═══════════════════════════════════════════════════════════════════
function moveCursor(x, y) {
  vcursor.style.display = 'block';
  vcursor.style.left = x + 'px';
  vcursor.style.top  = y + 'px';
  coordEl.style.display = 'block';
  coordEl.textContent = `${x} , ${y}`;
}

function ripple(x, y) {
  vring.style.left = x + 'px';
  vring.style.top  = y + 'px';
  vring.classList.remove('fire');
  void vring.offsetWidth;
  vring.classList.add('fire');
}

function injectClick(x, y, type='click') {
  try {
    const doc = uiFrame.contentDocument;
    if(!doc) return;
    const el = doc.elementFromPoint(x, y);
    if(!el) return;
    el.dispatchEvent(new MouseEvent(type,
      {bubbles:true,cancelable:true,clientX:x,clientY:y,
       view:uiFrame.contentWindow}));
    if(el.focus) el.focus();
  } catch(e){}
}

function injectKey(k, special=false) {
  try {
    const doc = uiFrame.contentDocument;
    if(!doc) return;
    const el = doc.activeElement || doc.body;
    ['keydown','keypress','keyup'].forEach(t =>
      el.dispatchEvent(new KeyboardEvent(t,
        {key:k,code:'Key'+k.toUpperCase(),bubbles:true,cancelable:true})));
  } catch(e){}
}

function injectInputValue(x, y, val) {
  try {
    const doc = uiFrame.contentDocument;
    if(!doc) return;
    const el = doc.elementFromPoint(x,y) || doc.activeElement;
    if(el && (el.tagName==='INPUT'||el.tagName==='TEXTAREA')) {
      el.value = val;
      el.dispatchEvent(new Event('input',{bubbles:true}));
      el.dispatchEvent(new Event('change',{bubbles:true}));
    }
  } catch(e){}
}

// ═══════════════════════════════════════════════════════════════════
//  KEYBOARD PiP
// ═══════════════════════════════════════════════════════════════════
function showKbd(on) {
  document.getElementById('kbd').classList.toggle('show', on);
  if(!on) {
    kbdBuf = '';
    document.getElementById('kbd-buf').textContent = '';
  }
}

function litKey(k, ms=200) {
  const el = keyEls[k.toLowerCase()] || keyEls[k];
  if(!el) return;
  el.classList.add('lit');
  setTimeout(() => el.classList.remove('lit'), ms);
}

// ═══════════════════════════════════════════════════════════════════
//  SCREENSHOT + FEEDBACK to agent
// ═══════════════════════════════════════════════════════════════════
function capture(mode, label) {
  const stage = document.getElementById('stage');
  html2canvas(stage, {
    useCORS:true, allowTaint:true, scale:0.8, logging:false
  }).then(canvas => {
    const b64 = canvas.toDataURL('image/jpeg', 0.72).split(',')[1];
    fetch('/feedback', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({b64, mode, label, ts:Date.now()})
    }).then(()=>{
      document.getElementById('fb-dot').classList.add('on');
      document.getElementById('fb-label').textContent =
        `${mode} · ${new Date().toLocaleTimeString()}`;
      setTimeout(()=>document.getElementById('fb-dot').classList.remove('on'), 900);
    }).catch(()=>{});
  }).catch(()=>{});
}

// ═══════════════════════════════════════════════════════════════════
//  ACTIVITY FEED
// ═══════════════════════════════════════════════════════════════════
function log(mode, action, ev) {
  const list = document.getElementById('feed-list');
  const item = document.createElement('div');
  const modeKey = {terminal:'term',web:'web',ui:'ui',sys:'term'}[mode]||'term';
  item.className = `feed-item ${modeKey}`;
  const t = new Date().toLocaleTimeString('en',{hour12:false,
    hour:'2-digit',minute:'2-digit',second:'2-digit'});
  const detail = ev.text||ev.url||ev.cmd||ev.html&&'[html]'||'';
  item.innerHTML =
    `<span class="fi-time">${t}</span>` +
    `<span class="fi-mode">${(mode||'sys').slice(0,3).toUpperCase()}</span>` +
    `${esc((action||''))} ${esc(String(detail).slice(0,40))}`;
  list.appendChild(item);
  list.scrollTop = list.scrollHeight;
  // keep feed trimmed
  while(list.children.length > 200) list.removeChild(list.firstChild);
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
</script>
</body>
</html>"""

# ── HTTP handler ──────────────────────────────────────────────────────────────
class _Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ('/', '/index.html'):
            self._send(200, 'text/html', _HTML.encode())
        elif p == '/activity':
            self._sse()
        elif p == '/screenshot':
            self._send(200, 'application/json', json.dumps(_last_screenshot).encode())
        else:
            self._send(404, 'text/plain', b'not found')

    def do_POST(self):
        p = urlparse(self.path).path
        n = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(n)
        try:
            data = json.loads(body)
        except Exception:
            self._send(400, 'text/plain', b'bad json'); return

        if p == '/push':
            _broadcast(data)
            self._send(200, 'application/json', b'{"ok":true}')
        elif p == '/feedback':
            _last_screenshot.update(data)
            self._send(200, 'application/json', b'{"ok":true}')
        else:
            self._send(404, 'text/plain', b'not found')

    def _send(self, code, ct, body):
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _sse(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        q: list = []
        with _lock:
            _activity_clients.append(q)
        try:
            while True:
                time.sleep(0.06)
                with _lock:
                    while q:
                        item = q.pop(0)
                        msg  = json.dumps(item)
                        self.wfile.write(f'data: {msg}\n\n'.encode())
                self.wfile.flush()
        except Exception:
            pass
        finally:
            with _lock:
                try: _activity_clients.remove(q)
                except ValueError: pass

    def log_message(self, *_): pass


def _broadcast(ev: dict):
    with _lock:
        for q in _activity_clients:
            q.append(ev)


# ── Agent-callable API ────────────────────────────────────────────────────────

def push(mode: str, action: str, **kwargs) -> bool:
    """Send any activity event to the PiP window."""
    import requests as _r
    payload = {"mode": mode, "action": action, **kwargs}
    try:
        _r.post(f"http://localhost:{PORT}/push", json=payload, timeout=1)
        return True
    except Exception:
        return False

# ── Terminal helpers ──────────────────────────────────────────────────────────

def term_type(cmd: str):
    """Animate agent typing a command."""
    push("terminal", "type", text=cmd)
    time.sleep(len(cmd) * 0.07 + 0.3)

def term_exec(cmd: str, sandbox: bool = True) -> str:
    """
    Execute a command in the sandbox dir, stream output to PiP.
    Returns combined stdout+stderr string.
    """
    push("terminal", "exec", cmd=cmd)
    cwd = str(SANDBOX_DIR) if sandbox else None
    out_lines = []
    try:
        proc = subprocess.Popen(
            shlex.split(cmd), cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1
        )
        for line in proc.stdout:
            push("terminal", "output", text=line.rstrip())
            out_lines.append(line)
        for line in proc.stderr:
            push("terminal", "output", text=line.rstrip(), stderr=True)
            out_lines.append(line)
        proc.wait()
    except Exception as e:
        push("terminal", "output", text=str(e), stderr=True)
    push("terminal", "output_done")
    return "".join(out_lines)

def term_run(cmd: str) -> str:
    """Type the command visually then execute it."""
    term_type(cmd)
    time.sleep(0.3)
    return term_exec(cmd)

# ── Web helpers ───────────────────────────────────────────────────────────────

def web_goto(url: str):
    push("web", "navigate", url=url)

def web_click(x: int, y: int):
    push("web", "click", x=x, y=y)

def web_type(text: str, x: int = 0, y: int = 0):
    push("web", "type", text=text, x=x, y=y)

def web_scroll(dy: int = 200):
    push("web", "scroll", dy=dy)

def web_load_html(html: str):
    push("web", "load_html", html=html)

# ── UI helpers ────────────────────────────────────────────────────────────────

def ui_push(html: str, label: str = "agent render"):
    push("ui", "push_html", html=html, label=label)

def ui_click(x: int, y: int):
    push("ui", "click", x=x, y=y)

def ui_type(text: str, x: int = 0, y: int = 0):
    push("ui", "type", text=text, x=x, y=y)

def ui_key(key: str):
    push("ui", "key", key=key)

def ui_scroll(dy: int = 120, selector: str = None):
    push("ui", "scroll", dy=dy, selector=selector)

# ── Screenshot ────────────────────────────────────────────────────────────────

def get_screenshot(wait: float = 1.5) -> str | None:
    import requests as _r
    time.sleep(wait)
    try:
        r = _r.get(f"http://localhost:{PORT}/screenshot", timeout=2)
        return r.json().get("b64")
    except Exception:
        return None

def preview_and_see(html: str, label: str = "agent render") -> dict:
    """Full loop: push UI → wait for render → return screenshot."""
    ok = ui_push(html=html, label=label)
    b64 = get_screenshot(wait=1.5)
    return {"html": html, "screenshot_b64": b64, "label": label}

# ── Server ────────────────────────────────────────────────────────────────────

def main(open_browser: bool = True):
    print(f"\n{PINK}{BOLD}  ╔══════════════════════════════════════════════════╗")
    print(f"  ║  SOV --UI  ·  AGENT ACTIVITY WINDOW            ║")
    print(f"  ╚══════════════════════════════════════════════════╝{RST}\n")
    print(f"  {LIME}✓{RST}  Window     : http://localhost:{PORT}")
    print(f"  {LIME}✓{RST}  Modes      : TERMINAL  |  WEB  |  UI")
    print(f"  {LIME}✓{RST}  Activity   : GET /activity  (SSE)")
    print(f"  {LIME}✓{RST}  Push       : POST /push  {{mode, action, …}}")
    print(f"  {LIME}✓{RST}  Screenshot : GET /screenshot")
    print(f"  {GRAY}    Agent sees every mode live — visual grounding active")
    print(f"    Ctrl+C to stop{RST}\n")

    if open_browser:
        def _open():
            time.sleep(0.55)
            webbrowser.open(f"http://localhost:{PORT}")
        threading.Thread(target=_open, daemon=True).start()

    class _TCP(socketserver.TCPServer):
        allow_reuse_address = True

    with _TCP(("", PORT), _Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print(f"\n  {GRAY}[sov-ui] stopped.{RST}")


if __name__ == "__main__":
    main()
