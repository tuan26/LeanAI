/* LeanAI — web app 90 ngày */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const api = async (url, opts) => {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const post = (url, body) => api(url, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body || {})
});
const vnd = n => new Intl.NumberFormat('vi-VN').format(n);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const state = { ov: null, day: null, sideView: 'dashboard', collapsed: {} };

/* ------------------------------------------------------------ toast */
let toastT;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg; t.hidden = false;
  clearTimeout(toastT);
  toastT = setTimeout(() => (t.hidden = true), 2600);
}

/* ------------------------------------------------------------ theme */
function initTheme() {
  const saved = localStorage.getItem('leanai-theme');
  if (saved) document.documentElement.dataset.theme = saved;
  $('#btn-theme').onclick = () => {
    const cur = document.documentElement.dataset.theme;
    const dark = cur ? cur === 'dark'
      : matchMedia('(prefers-color-scheme: dark)').matches;
    const next = dark ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('leanai-theme', next);
  };
}

/* ------------------------------------------------------------ overview */
async function loadOverview() {
  state.ov = await api('/api/overview');
  renderTop();
  renderSidebar();
  return state.ov;
}

function renderTop() {
  const o = state.ov;
  $('#tp-fill').style.width = (o.passed / 90 * 100) + '%';
  $('#tp-label').textContent = `${o.passed}/90`;
  const b = $('#due-badge');
  if (o.quiz.due > 0) { b.textContent = o.quiz.due; b.hidden = false; }
  else b.hidden = true;
}

/* ------------------------------------------------------------ sidebar */
function renderSidebar() {
  $$('.tab').forEach(t => t.classList.toggle('active', t.dataset.view === state.sideView));
  $('#side-body').innerHTML =
    state.sideView === 'lessons' ? sidebarLessons() : sidebarDashboard();
  bindSidebar();
}

function sidebarLessons() {
  const o = state.ov;
  return o.phases.map(p => {
    const days = o.days.filter(d => d.day >= p.lo && d.day <= p.hi);
    const open = state.collapsed[p.num] !== true;
    return `<div class="phase-group">
      <div class="phase-head" data-phase="${p.num}">
        <span>${open ? '▾' : '▸'}</span>
        <span class="phase-name">P${p.num} · ${esc(p.name)}</span>
        <span class="phase-count">${p.done}/${p.total}</span>
      </div>
      <div class="phase-bar"><div style="width:${p.pct * 100}%"></div></div>
      ${open ? days.map(dayItem).join('') : ''}
    </div>`;
  }).join('');
}

function dayItem(d) {
  const cls = d.status === 'pass' ? 'pass' : d.status === 'fail' ? 'fail'
    : d.is_next ? 'next' : '';
  const flag = d.milestone ? '<span class="di-flag ms">🚀</span>'
    : d.quiz_due ? `<span class="di-flag">${d.quiz_due} ôn</span>` : '';
  return `<div class="day-item ${state.day === d.day ? 'active' : ''}" data-day="${d.day}">
    <span class="di-dot ${cls}"></span>
    <span class="di-num">${d.day}</span>
    <span class="di-title">${esc(d.title)}</span>${flag}</div>`;
}

function sidebarDashboard() {
  const o = state.ov;
  const mastery = o.quiz.total ? o.quiz.mastered / o.quiz.total : 0;
  const costPct = o.budget ? Math.min(o.cost / o.budget, 1) : 0;
  const costColor = costPct > .9 ? 'var(--er)' : costPct > .7 ? 'var(--wa)' : 'var(--ok)';
  const nextD = o.days.find(d => d.day === o.next_day);

  return `
  <div class="stat-row"><span class="k">Hoàn thành</span>
    <span class="v">${o.passed}/90</span></div>
  <div class="mini-bar"><div style="width:${o.passed / 90 * 100}%;background:var(--ok)"></div></div>

  <div class="stat-row"><span class="k">Quiz đã thuộc</span>
    <span class="v">${o.quiz.mastered}/${o.quiz.total}</span></div>
  <div class="mini-bar"><div style="width:${mastery * 100}%;background:var(--cy)"></div></div>

  <div class="stat-row"><span class="k">Chi phí API</span>
    <span class="v">$${o.cost.toFixed(2)} / $${o.budget.toFixed(0)}</span></div>
  <div class="mini-bar"><div style="width:${costPct * 100}%;background:${costColor}"></div></div>

  <div class="stat-row"><span class="k">Chuỗi ngày</span><span class="v">${o.streak}</span></div>
  <div class="stat-row"><span class="k">Giờ học</span>
    <span class="v">${(o.minutes / 60).toFixed(1)}h</span></div>
  <div class="stat-row"><span class="k">Commit</span><span class="v">${o.commits}</span></div>
  <div class="stat-row"><span class="k">Quiz đến hạn</span>
    <span class="v" style="color:${o.quiz.due ? 'var(--wa)' : 'inherit'}">${o.quiz.due}</span></div>

  ${nextD ? `<div class="sec-title">Tiếp theo</div>
    <div class="day-item" data-day="${nextD.day}" style="background:var(--panel2)">
      <span class="di-dot next"></span><span class="di-num">${nextD.day}</span>
      <span class="di-title">${esc(nextD.title)}</span></div>` : ''}

  ${o.debt.length ? `<div class="warn-box">
      <b>Nợ ${o.debt.length} ngày:</b> ${o.debt.slice(0, 12).join(', ')}
      ${o.debt.length > o.max_debt
      ? `<div style="margin-top:6px;color:var(--er)">Quá ${o.max_debt} ngày nợ —
         dừng học mới, quay lại Ngày ${o.debt[0]}.</div>` : ''}
    </div>` : ''}

  <div class="sec-title">90 ngày</div>
  <div class="grid90">${o.days.map(d =>
    `<div class="g-cell ${d.status === 'pass' ? 'pass' : d.status === 'fail' ? 'fail' : ''}
      ${d.is_next ? 'next' : ''}" data-day="${d.day}"
      title="Ngày ${d.day}: ${esc(d.title)}"></div>`).join('')}</div>

  <div class="sec-title">Mốc sản phẩm</div>
  ${o.milestones.map(m => `<div class="ms-row ${m.done ? 'done' : ''}" data-day="${m.day}"
      style="cursor:pointer"><span class="ms-dot"></span>Ngày ${m.day} — ${esc(m.name)}</div>`).join('')}
  `;
}

function bindSidebar() {
  $$('[data-day]', $('#side-body')).forEach(el =>
    el.onclick = () => go(+el.dataset.day));
  $$('.phase-head').forEach(el => el.onclick = () => {
    const p = el.dataset.phase;
    state.collapsed[p] = !state.collapsed[p];
    renderSidebar();
  });
}

/* ------------------------------------------------------------ views */
async function go(day) {
  location.hash = day ? `#/day/${day}` : '#/';
}

async function route() {
  const m = location.hash.match(/#\/day\/(\d+)/);
  if (m) { state.day = +m[1]; state.sideView = 'lessons'; await renderLesson(+m[1]); }
  else { state.day = null; await renderDashboard(); }
  renderSidebar();
  $('#main').scrollTop = 0;
  $('#sidebar').classList.remove('open');
}

/* -------------------------------------------------- dashboard (main) */
async function renderDashboard() {
  const o = state.ov || await loadOverview();
  const mastery = o.quiz.total ? o.quiz.mastered / o.quiz.total : 0;
  const weeks = o.passed ? ((90 - o.passed) / Math.max(o.streak ? 5 : 5, 1)).toFixed(0) : '—';

  $('#main').innerHTML = `
  <div class="lesson-head">
    <div class="lh-left">
      <div class="lh-kicker">Tổng quan</div>
      <div class="lh-title">Tiến trình 90 ngày</div>
      <div class="lh-meta">
        <span class="pill">${o.passed}/90 ngày</span>
        <span class="pill">${o.quiz.mastered}/${o.quiz.total} câu đã thuộc</span>
        <span class="pill">$${o.cost.toFixed(2)} đã tiêu</span>
        ${o.debt.length ? `<span class="pill er">nợ ${o.debt.length} ngày</span>` : ''}
      </div>
    </div>
    <div class="lh-actions">
      ${o.quiz.due ? `<button class="btn primary" id="d-review">Ôn ${o.quiz.due} câu đến hạn</button>` : ''}
      ${o.next_day ? `<button class="btn" id="d-next">Vào Ngày ${o.next_day} →</button>` : ''}
    </div>
  </div>

  <div class="dash-grid">
    ${card('Hoàn thành', `${o.passed}<span style="font-size:15px;color:var(--mut)">/90</span>`,
    `${(o.passed / 90 * 100).toFixed(0)}%`)}
    ${card('Quiz đã thuộc', `${(mastery * 100).toFixed(0)}%`, `${o.quiz.mastered}/${o.quiz.total} câu`)}
    ${card('Chi phí API', `$${o.cost.toFixed(2)}`, `ngân sách $${o.budget.toFixed(0)}`)}
    ${card('Giờ học', `${(o.minutes / 60).toFixed(1)}h`, `${o.minutes} phút`)}
    ${card('Chuỗi ngày', o.streak, o.streak ? 'liên tiếp' : 'chưa bắt đầu')}
    ${card('Commit', o.commits, 'mục tiêu ≥ 90')}
  </div>

  <div class="panel">
    <h3>Theo giai đoạn</h3>
    ${o.phases.map(p => `<div class="prow">
      <div class="nm">P${p.num} · ${esc(p.name)}</div>
      <div class="tr"><div style="width:${p.pct * 100}%;background:${p.pct >= 1 ? 'var(--ok)' : 'var(--cy)'}"></div></div>
      <div class="vl">${p.done}/${p.total}</div></div>`).join('')}
  </div>

  <div class="panel">
    <h3>90 ngày</h3>
    <div class="big-grid">${o.days.map(d =>
      `<div class="g-cell ${d.status === 'pass' ? 'pass' : d.status === 'fail' ? 'fail' : ''}
        ${d.is_next ? 'next' : ''}" data-day="${d.day}"
        title="Ngày ${d.day}: ${esc(d.title)}${d.milestone ? ' 🚀' : ''}"></div>`).join('')}
    </div>
    <div style="margin-top:12px;font-size:12px;color:var(--mut)">
      <span style="color:var(--ok)">■</span> PASS &nbsp;
      <span style="color:var(--er)">■</span> FAIL &nbsp;
      <span style="color:var(--accent)">▢</span> ngày kế tiếp
    </div>
  </div>

  <div class="panel">
    <h3>Trí nhớ — phân bố hộp Leitner</h3>
    ${Object.entries(o.quiz.boxes).map(([b, n]) => {
      const days = [0, 1, 2, 4, 8, 16][b - 1] ?? 0;
      const max = Math.max(...Object.values(o.quiz.boxes), 1);
      return `<div class="prow"><div class="nm">Hộp ${b} · ôn sau ${days} ngày</div>
      <div class="tr"><div style="width:${n / max * 100}%;background:${b >= 5 ? 'var(--ok)' : 'var(--cy)'}"></div></div>
      <div class="vl">${n}</div></div>`;
    }).join('')}
    <div style="font-size:12.5px;color:var(--mut);margin-top:10px">
      Câu ở hộp 5–6 được tính là <b>đã thuộc</b>. Trả lời sai thì câu rơi về hộp 1.
    </div>
  </div>

  <div class="panel">
    <h3>Mốc sản phẩm</h3>
    ${o.milestones.map(m => `<div class="ms-row ${m.done ? 'done' : ''}" data-day="${m.day}"
      style="cursor:pointer;font-size:14px;padding:6px 0">
      <span class="ms-dot"></span>Ngày ${m.day} — ${esc(m.name)}</div>`).join('')}
  </div>`;

  $$('[data-day]', $('#main')).forEach(el => el.onclick = () => go(+el.dataset.day));
  const rv = $('#d-review'); if (rv) rv.onclick = () => openQuiz({ mode: 'review' });
  const nx = $('#d-next'); if (nx) nx.onclick = () => go(o.next_day);
}

const card = (k, v, sub) =>
  `<div class="card"><div class="k">${k}</div><div class="v">${v}</div>
   <div class="sub">${sub}</div></div>`;

/* ----------------------------------------------------- lesson (main) */
async function renderLesson(day) {
  $('#main').innerHTML = '<div class="loading">Đang tải bài học…</div>';
  let d;
  try { d = await api('/api/day/' + day); }
  catch (e) { $('#main').innerHTML = `<div class="loading">Lỗi: ${esc(e.message)}</div>`; return; }

  const st = d.state || {};
  const statusPill = st.status === 'pass'
    ? '<span class="pill ok">✓ PASS</span>'
    : st.status === 'fail' ? '<span class="pill er">✗ FAIL</span>' : '';

  $('#main').innerHTML = `
  <div class="lesson-head">
    <div class="lh-left">
      <div class="lh-kicker">Phase ${d.phase} · Ngày ${d.day}/90
        ${d.milestone ? ' · 🚀 ' + esc(d.milestone) : ''}</div>
      <div class="lh-title">${esc(d.title)}</div>
      <div class="lh-meta">
        ${statusPill}
        ${st.date ? `<span class="pill">học ${st.date}</span>` : ''}
        ${st.minutes ? `<span class="pill">${st.minutes} phút</span>` : ''}
        ${st.cost ? `<span class="pill">$${Number(st.cost).toFixed(3)}</span>` : ''}
        <span class="pill">${st.quiz_total || 0} câu quiz</span>
        ${st.quiz_mastered ? `<span class="pill ok">${st.quiz_mastered} đã thuộc</span>` : ''}
        <span class="pill">${esc(d.file)}</span>
      </div>
    </div>
    <div class="lh-actions">
      <button class="btn" id="l-quiz">Làm quiz (${st.quiz_total || 0})</button>
      <button class="btn primary" id="l-done">${st.status === 'pass' ? 'Cập nhật' : 'Đánh dấu xong'}</button>
    </div>
  </div>

  <article class="article">${d.html}</article>

  <div class="lesson-foot">
    ${d.prev ? `<button class="btn" data-goto="${d.prev}">← Ngày ${d.prev}</button>` : '<span></span>'}
    ${d.next ? `<button class="btn" data-goto="${d.next}">Ngày ${d.next} →</button>` : '<span></span>'}
  </div>`;

  enhanceCode();
  $$('[data-goto]').forEach(b => b.onclick = () => go(+b.dataset.goto));
  $('#l-quiz').onclick = () => openQuiz({ mode: 'day', day });
  $('#l-done').onclick = () => openDone(d);
}

function enhanceCode() {
  $$('.article pre').forEach(pre => {
    const btn = document.createElement('button');
    btn.className = 'copy-btn'; btn.textContent = 'copy';
    btn.onclick = async () => {
      await navigator.clipboard.writeText(pre.innerText.replace(/^copy\n?/, ''));
      btn.textContent = 'đã copy'; btn.classList.add('done');
      setTimeout(() => { btn.textContent = 'copy'; btn.classList.remove('done'); }, 1600);
    };
    pre.appendChild(btn);
  });
}

/* ------------------------------------------------------------ quiz */
const quiz = { items: [], i: 0, right: 0, wrong: [], label: '', answered: false };

async function openQuiz({ mode = 'day', day = null }) {
  let data;
  try {
    data = await api(`/api/quiz?mode=${mode}${day ? '&day=' + day : ''}`);
  } catch (e) { toast('Lỗi: ' + e.message); return; }

  if (!data.count) {
    toast(mode === 'review' ? 'Không có câu nào đến hạn ôn. Nghỉ ngơi.'
      : 'Ngày này chưa có câu hỏi.');
    return;
  }
  quiz.items = data.questions; quiz.i = 0; quiz.right = 0; quiz.wrong = [];
  quiz.label = mode === 'review' ? 'Ôn tập đến hạn'
    : mode === 'weak' ? 'Câu yếu nhất' : `Quiz Ngày ${day}`;
  $('#quiz-title').textContent = quiz.label;
  $('#quiz-modal').hidden = false;
  showQuestion();
}

function showQuestion() {
  const q = quiz.items[quiz.i];
  if (!q) return showResult();
  quiz.answered = false;
  $('#quiz-sub').textContent =
    `Câu ${quiz.i + 1}/${quiz.items.length} · Ngày ${q.day} — ${q.topic}` +
    (q.box ? ` · hộp ${q.box}` : ' · câu mới');
  $('#quiz-bar').style.width = (quiz.i / quiz.items.length * 100) + '%';

  let body = `<div class="q-text">${esc(q.q)}</div>`;
  if (q.type === 'mcq') {
    body += q.choices.map((c, i) =>
      `<button class="choice" data-i="${i}">
         <span class="ltr">${String.fromCharCode(65 + i)}.</span>${esc(c)}</button>`).join('');
  } else if (q.type === 'open') {
    body += `<textarea class="q-input" id="q-ans" placeholder="Viết câu trả lời của bạn…"></textarea>`;
  } else {
    body += `<div style="color:var(--mut);font-size:14px">Nghĩ 10 giây rồi lật đáp án.</div>`;
  }
  $('#quiz-body').innerHTML = body;

  const foot = $('#quiz-foot');
  if (q.type === 'mcq') {
    foot.innerHTML = `<button class="btn ghost" id="q-skip">Bỏ qua</button>`;
    $$('.choice').forEach(b => b.onclick = () => answerMcq(+b.dataset.i));
    $('#q-skip').onclick = () => submit(false);
  } else {
    foot.innerHTML = `<button class="btn primary" id="q-reveal">Lật đáp án</button>`;
    $('#q-reveal').onclick = reveal;
  }
}

async function answerMcq(choice) {
  if (quiz.answered) return;
  quiz.answered = true;
  const q = quiz.items[quiz.i];
  let res;
  try { res = await post('/api/quiz/answer', { qid: q.id, choice }); }
  catch (e) { toast(e.message); return; }

  $$('.choice').forEach((b, i) => {
    b.disabled = true;
    if (i === res.right_index) b.classList.add('correct');
    else if (i === choice) b.classList.add('wrong');
  });
  if (res.correct) quiz.right++; else quiz.wrong.push(q);
  showExplain(q, res.correct);
}

function reveal() {
  const q = quiz.items[quiz.i];
  const mine = q.type === 'open' ? ($('#q-ans')?.value || '') : '';
  let kw = '';
  if (q.keywords?.length) {
    kw = '<div style="margin-top:8px">' + q.keywords.map(k =>
      `<span class="kw ${mine.toLowerCase().includes(k.toLowerCase()) ? 'hit' : ''}">${esc(k)}</span>`
    ).join('') + '</div>';
  }
  $('#quiz-body').insertAdjacentHTML('beforeend',
    `<div class="reveal"><div class="lbl">Đáp án tham khảo</div>${esc(q.answer)}${kw}</div>`);
  $('#quiz-foot').innerHTML =
    `<span style="margin-right:auto;color:var(--mut);font-size:13px">Bạn trả lời đúng không?</span>
     <button class="btn danger ghost" id="q-no">Chưa đúng</button>
     <button class="btn primary" id="q-yes">Đúng</button>`;
  $('#q-yes').onclick = () => submit(true);
  $('#q-no').onclick = () => submit(false);
}

async function submit(correct) {
  if (quiz.answered && correct === false && quiz.items[quiz.i].type === 'mcq') return;
  const q = quiz.items[quiz.i];
  try { await post('/api/quiz/answer', { qid: q.id, correct }); }
  catch (e) { toast(e.message); }
  if (correct) quiz.right++; else quiz.wrong.push(q);
  showExplain(q, correct);
}

function showExplain(q, correct) {
  if (q.explain) {
    $('#quiz-body').insertAdjacentHTML('beforeend',
      `<div class="explain">${esc(q.explain)}</div>`);
  }
  $('#quiz-foot').innerHTML =
    `<span style="margin-right:auto;font-weight:600;color:${correct ? 'var(--ok)' : 'var(--er)'}">
       ${correct ? '✓ Đúng' : '✗ Sai — câu này sẽ quay lại sớm'}</span>
     <button class="btn primary" id="q-next">
       ${quiz.i + 1 < quiz.items.length ? 'Câu tiếp →' : 'Xem kết quả'}</button>`;
  $('#q-next').onclick = () => { quiz.i++; showQuestion(); };
}

async function showResult() {
  const n = quiz.items.length;
  const pct = Math.round(quiz.right / n * 100);
  const pass = pct >= 80;
  $('#quiz-bar').style.width = '100%';
  $('#quiz-sub').textContent = 'Hoàn thành';
  $('#quiz-body').innerHTML = `
    <div class="result-big">
      <div class="score" style="color:${pass ? 'var(--ok)' : 'var(--wa)'}">${quiz.right}/${n}</div>
      <div style="color:var(--mut)">${pct}%</div>
      <div class="verdict ${pass ? 'pass' : 'fail'}">
        ${pass ? 'PASS — đủ điều kiện sang ngày mới'
      : 'CHƯA PASS — cần ≥ 80%. Đọc lại phần lý thuyết rồi làm lại.'}</div>
      ${quiz.wrong.length ? `<ul class="wrong-list">
        <div style="font-weight:600;color:var(--tx);margin-bottom:6px">Câu còn sai:</div>
        ${quiz.wrong.map(w => `<li>[Ngày ${w.day}] ${esc(w.q)}</li>`).join('')}</ul>` : ''}
    </div>`;
  $('#quiz-foot').innerHTML = `<button class="btn primary" id="q-done">Đóng</button>`;
  $('#q-done').onclick = closeQuiz;
  try { await post('/api/quiz/session', { label: quiz.label, right: quiz.right, total: n }); }
  catch { }
  await loadOverview();
}

async function closeQuiz() {
  $('#quiz-modal').hidden = true;
  await loadOverview();
  if (state.day) renderLesson(state.day); else renderDashboard();
}

/* ------------------------------------------------------------ mark done */
let doneDay = null;
function openDone(d) {
  doneDay = d.day;
  const st = d.state || {};
  $('#done-title').textContent = `Ngày ${d.day} — ${d.title}`;
  $('#f-minutes').value = st.minutes || 120;
  $('#f-cost').value = st.cost || 0;
  $('#f-note').value = st.note || '';
  $('#f-criteria').innerHTML = d.pass_criteria.length
    ? '<div class="sec-title" style="margin-top:4px">Tiêu chí PASS</div>' +
    d.pass_criteria.map(c => `<div class="ci">☐ ${esc(c)}</div>`).join('')
    : '';
  $('#done-modal').hidden = false;
}

async function mark(status) {
  await post(`/api/day/${doneDay}/status`, {
    status,
    minutes: +$('#f-minutes').value || 0,
    cost: +$('#f-cost').value || 0,
    note: $('#f-note').value.trim(),
  });
  $('#done-modal').hidden = true;
  toast(status === 'pass' ? `Ngày ${doneDay}: PASS ✓` : `Ngày ${doneDay}: FAIL`);
  await loadOverview();
  renderLesson(doneDay);
}

/* ------------------------------------------------------------ search */
let searchT;
function initSearch() {
  const box = $('#search'), out = $('#search-results');
  box.oninput = () => {
    clearTimeout(searchT);
    const q = box.value.trim();
    if (q.length < 2) { out.hidden = true; return; }
    searchT = setTimeout(async () => {
      const { results } = await api('/api/search?q=' + encodeURIComponent(q));
      out.innerHTML = results.length
        ? results.map(r => `<div class="sr-item" data-day="${r.day}">
            <div class="sr-day">Ngày ${r.day} · Phase ${r.phase} · ${r.hits} kết quả</div>
            <div class="sr-title">${esc(r.title)}</div>
            <div class="sr-snip">${esc(r.snippet)}</div></div>`).join('')
        : '<div class="sr-item" style="color:var(--mut)">Không tìm thấy</div>';
      out.hidden = false;
      $$('.sr-item[data-day]').forEach(el => el.onclick = () => {
        go(+el.dataset.day); out.hidden = true; box.value = '';
      });
    }, 220);
  };
  document.addEventListener('click', e => {
    if (!e.target.closest('.search-wrap')) out.hidden = true;
  });
}

/* ------------------------------------------------------------ init */
function init() {
  initTheme();
  initSearch();
  $$('.tab').forEach(t => t.onclick = () => { state.sideView = t.dataset.view; renderSidebar(); });
  $('#btn-menu').onclick = () => $('#sidebar').classList.toggle('open');
  $('#btn-review').onclick = () => openQuiz({ mode: 'review' });
  $('#quiz-close').onclick = closeQuiz;
  $('#done-close').onclick = () => ($('#done-modal').hidden = true);
  $('#btn-mark-pass').onclick = () => mark('pass');
  $('#btn-mark-fail').onclick = () => mark('fail');
  $('.brand').onclick = e => { e.preventDefault(); go(null); };

  document.addEventListener('keydown', e => {
    if (e.target.matches('input,textarea')) return;
    if (e.key === 'Escape') { $('#quiz-modal').hidden = true; $('#done-modal').hidden = true; }
    if (e.key === '/') { e.preventDefault(); $('#search').focus(); }
    if (!$('#quiz-modal').hidden) {
      const q = quiz.items[quiz.i];
      if (q?.type === 'mcq' && /^[a-f]$/i.test(e.key)) {
        const b = $$('.choice')[e.key.toLowerCase().charCodeAt(0) - 97];
        if (b && !b.disabled) b.click();
      }
      if (e.key === 'Enter') { $('#q-next')?.click(); $('#q-reveal')?.click(); }
      return;
    }
    if (state.day) {
      if (e.key === 'ArrowLeft' && state.day > 1) go(state.day - 1);
      if (e.key === 'ArrowRight' && state.day < 90) go(state.day + 1);
    }
  });

  addEventListener('hashchange', route);
  loadOverview().then(route);
}

init();
