/* ══════════════════════════════════════════════════════════════════
   ایجنت ویندوز — پنل ویندوز · منطق رابط کاربری
   هر ۰.۷ ثانیه وضعیت از پایتون (window.pywebview.api.get_state) گرفته
   و صفحه با همان وضعیت تازه می‌شود. هیچ منطقی اینجا تصمیم نمی‌گیرد؛
   فقط نمایش و صدا زدن متدهای پایتون.
   ══════════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  var POLL_MS = 700;
  var FA = '۰۱۲۳۴۵۶۷۸۹';
  var MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
  var WEEKDAYS = ['شنبه', 'یک‌شنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه'];

  var TABS = [
    [
      { id: 'main', label: 'مغز ایجنت' },
      { id: 'mother', label: 'ایجنت مادر' },
      { id: 'collab', label: 'ایجنت همکار' },
      { id: 'manage', label: 'ایجنت مدیریت' }
    ],
    [
      { id: 'codes', label: 'کتابخانه کدها' },
      { id: 'shots', label: 'اسکرین‌شات‌ها' },
      { id: 'live', label: 'گزارش زنده' },
      { id: 'changes', label: 'تغییرات' }
    ]
  ];

  var CHANGELOG = [
    {
      v: '۱.۶', d: '۱۴۰۵/۰۸/۰۲',
      items: [
        'رابط کاربری از pygame به یک صفحه‌ی وب داخلی (pywebview) منتقل شد.',
        'کارت‌های گرد، فونت وزیرمتن، دو ردیف تب و ظاهر تازه با همان هشت بخش.',
        'همه‌ی منطق قبلی دست‌نخورده ماند: بررسی مخزن، اجرای کدها، اسکرین‌شات، گزارش.',
        'حالت دستی/خودکار، تم تاریک و روشن، صدا و بی‌صدا همه مثل قبل کار می‌کنند.'
      ]
    },
    {
      v: '۱.۵', d: '۱۴۰۵/۰۸/۰۱',
      items: [
        'به‌روزرسانی خودکار حذف شد؛ نسخه‌ها دستی با GitHub Desktop منتشر می‌شوند.',
        'هشت تب در دو ردیف، هدر برند + نشان «پنل ویندوز».',
        'تب ایجنت مدیریت با شرح مخزن‌های در اختیار.'
      ]
    },
    {
      v: '۱.۴', d: '۱۴۰۵/۰۸/۰۱',
      items: ['فونت‌ها بزرگ‌تر شدند.', 'دکمه‌ی بی‌صدا در هدر.', 'تب‌ها از راست چیده شدند.']
    },
    {
      v: '۱.۳', d: '۱۴۰۵/۰۸/۰۱',
      items: ['رابط گرافیکی با صدا، تایمر دایره‌ای حالت خودکار و کتابخانه کدها.']
    },
    {
      v: '۱.۲', d: '۱۴۰۵/۰۸/۰۱',
      items: ['تم تاریک/روشن، فونت وزیرمتن، تب‌های قرصی و کلید حالت.']
    },
    {
      v: '۱.۱', d: '۱۴۰۵/۰۸/۰۱',
      items: ['هیچ فایلی کنار app.py نوشته نمی‌شود؛ تنظیمات در LOCALAPPDATA.', 'همه‌ی خطاها در logs/errors گوگل درایو.']
    },
    {
      v: '۱.۰', d: '۱۴۰۵/۰۸/۰۱',
      items: ['پوشه‌ی CODES روی دسکتاپ؛ تماشای مخزن همکار و اجرای فایل‌های پایتون.']
    }
  ];

  /* ─────────────────────────────── ابزارک ─────────────────────────────── */

  function $(id) { return document.getElementById(id); }

  function fa(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/[0-9]/g, function (d) { return FA[+d]; });
  }

  function esc(text) {
    return String(text === null || text === undefined ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function g2j(gy, gm, gd) {
    var gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    var jy = gy <= 1600 ? 0 : 979;
    gy -= gy <= 1600 ? 621 : 1600;
    var gy2 = gm > 2 ? gy + 1 : gy;
    var days = 365 * gy + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) +
      Math.floor((gy2 + 399) / 400) - 80 + gd + gdm[gm - 1];
    jy += 33 * Math.floor(days / 12053); days %= 12053;
    jy += 4 * Math.floor(days / 1461); days %= 1461;
    if (days > 365) { jy += Math.floor((days - 1) / 365); days = (days - 1) % 365; }
    var jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
    var jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
    return [jy, jm, jd];
  }

  var SVG_PLAY = '<svg viewBox="0 0 24 24"><path d="M8 5l11 7-11 7z"/></svg>';

  /* ─────────────────────────────── صدا ─────────────────────────────── */

  var sounds = {};

  function play(name) {
    if (!state || state.muted) return;
    try {
      var node = (sounds[name] || (sounds[name] = new Audio('/sounds/' + name + '.wav')));
      var copy = node.cloneNode();
      copy.volume = 0.55;
      var p = copy.play();
      if (p && p.catch) p.catch(function () { });
    } catch (e) { /* بی‌صدا رد شو */ }
  }

  /* ─────────────────────────────── وضعیت ─────────────────────────────── */

  var state = null;
  var activeTab = null;
  var collabDirty = false;
  var sig = { codes: '', shots: '', log: '', paths: '', chips: '', fields: '' };
  var pendingConfirm = null;

  function api() {
    return (window.pywebview && window.pywebview.api) || null;
  }

  /* ─────────────────────────────── تب‌ها ─────────────────────────────── */

  function buildTabs() {
    TABS.forEach(function (row, index) {
      var box = $('tabs-row-' + (index + 1));
      row.forEach(function (tab) {
        var btn = document.createElement('button');
        btn.className = 'tab';
        btn.type = 'button';
        btn.dataset.tab = tab.id;
        btn.textContent = tab.label;
        btn.addEventListener('click', function () { setTab(tab.id); });
        box.appendChild(btn);
      });
    });
    var saved = null;
    try { saved = localStorage.getItem('wa.tab'); } catch (e) { }
    var ok = TABS[0].concat(TABS[1]).some(function (t) { return t.id === saved; });
    setTab(ok ? saved : 'main');
  }

  function setTab(name) {
    activeTab = name;
    Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (b) {
      b.classList.toggle('active', b.dataset.tab === name);
    });
    Array.prototype.forEach.call(document.querySelectorAll('.view'), function (v) {
      v.classList.toggle('active', v.dataset.tab === name);
    });
    try { localStorage.setItem('wa.tab', name); } catch (e) { }
    if (name === 'live') scrollLogToEnd();
  }

  function setBadge(tabId, count) {
    var btn = document.querySelector('.tab[data-tab="' + tabId + '"]');
    if (!btn) return;
    var badge = btn.querySelector('.count');
    if (!count) {
      if (badge) badge.remove();
      return;
    }
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'count';
      btn.appendChild(badge);
    }
    badge.textContent = fa(count);
  }

  /* ─────────────────────────────── ساعت و تاریخ ─────────────────────────────── */

  function tickClock() {
    var now = new Date();
    var hh = String(now.getHours()).padStart(2, '0');
    var mm = String(now.getMinutes()).padStart(2, '0');
    var ss = String(now.getSeconds()).padStart(2, '0');
    $('clock').textContent = fa(hh + ':' + mm + ':' + ss);
    var j = g2j(now.getFullYear(), now.getMonth() + 1, now.getDate());
    var wd = WEEKDAYS[(now.getDay() + 1) % 7];
    $('date').textContent = wd + ' ' + fa(j[2]) + ' ' + MONTHS[j[1] - 1] + ' ' + fa(j[0]);
  }

  /* ─────────────────────────────── رندر ─────────────────────────────── */

  function applyState(s) {
    if (!s || s.version === undefined) return;
    state = s;

    document.documentElement.dataset.theme = s.theme === 'light' ? 'light' : 'dark';

    $('version').textContent = s.version_fa || fa(s.version);
    $('build').textContent = s.build || '—';

    $('mute-btn').classList.toggle('active', !!s.muted);
    $('theme-btn').title = s.theme === 'light' ? 'رفتن به تم تاریک' : 'رفتن به تم روشن';

    renderMode(s);
    renderStats(s);
    renderPaths(s);
    renderCodes(s);
    renderShots(s);
    renderLog(s);
    renderStatus(s);
    renderRepo(s);
    renderManage(s);
    renderEvents(s.events);
  }

  function renderMode(s) {
    var ring = $('ring');
    var num = $('ring-number');
    var label = $('ring-label');
    var title = $('mode-title');
    var hint = $('mode-hint');
    var sw = $('auto-switch');

    sw.checked = !!s.auto;
    document.body.classList.toggle('busy', !!s.busy);

    var total = 263.9;
    var fraction = 0;

    if (s.busy) {
      title.textContent = 'در حال کار';
      title.classList.add('on');
      hint.textContent = s.busy;
      num.textContent = '…';
      label.textContent = 'صبر کن';
      fraction = 0.35;
      ring.classList.remove('warn');
    } else if (s.auto) {
      title.textContent = 'خودکار';
      title.classList.add('on');
      hint.textContent = 'هر ' + fa(s.auto_total) + ' ثانیه مخزن همکار بررسی می‌شود؛ بدون پرسیدن.';
      num.textContent = fa(Math.ceil(s.auto_remaining));
      label.textContent = 'تا دور بعد';
      fraction = s.auto_total ? Math.max(0, Math.min(1, 1 - s.auto_remaining / s.auto_total)) : 0;
      ring.classList.toggle('warn', s.auto_remaining <= 3);
    } else {
      title.textContent = 'دستی';
      title.classList.remove('on');
      hint.textContent = 'هیچ کاری بدون اجازه‌ی تو انجام نمی‌شود.';
      num.textContent = '—';
      label.textContent = 'دستی';
      fraction = 0;
      ring.classList.remove('warn');
    }

    ring.style.strokeDashoffset = String(total * (1 - fraction));
  }

  function renderStats(s) {
    var codes = s.codes || [];
    var done = codes.filter(function (c) { return c.ran; }).length;
    $('stat-total').textContent = fa(codes.length);
    $('stat-done').textContent = fa(done);
    $('stat-pending').textContent = fa(codes.length - done);
    setBadge('codes', codes.length - done);
    $('codes-count').textContent = codes.length ? fa(codes.length) + ' فایل' : '';
    $('shots-count').textContent = (s.shots || []).length ? fa((s.shots || []).length) + ' تصویر' : '';
  }

  var PATH_LABELS = [
    ['codes', 'پوشه کدها'],
    ['logs', 'پوشه گزارش‌ها'],
    ['errors', 'پوشه خطاها'],
    ['shots', 'پوشه اسکرین‌شات‌ها'],
    ['state', 'تنظیمات برنامه']
  ];

  function renderPaths(s) {
    var paths = s.paths || {};
    var key = JSON.stringify(paths);
    if (key === sig.paths) return;
    sig.paths = key;

    var box = $('paths');
    box.innerHTML = '';
    PATH_LABELS.forEach(function (pair) {
      var value = paths[pair[0]];
      if (!value) return;
      var row = document.createElement('div');
      row.className = 'path-row';
      row.innerHTML =
        '<dt>' + esc(pair[1]) + '</dt>' +
        '<dd title="' + esc(value) + '">' + esc(value) + '</dd>' +
        '<button class="btn btn-ghost small-btn" type="button" data-open="' + pair[0] + '">باز کردن</button>';
      box.appendChild(row);
    });

    $('codes-path').textContent = paths.codes || '—';
    $('shots-path').textContent = paths.shots || '—';
  }

  function renderCodes(s) {
    var codes = s.codes || [];
    var key = JSON.stringify(codes);
    if (key === sig.codes) return;
    sig.codes = key;

    var list = $('codes-list');
    var empty = $('codes-empty');
    empty.classList.toggle('hidden', codes.length > 0);
    list.innerHTML = '';

    codes.forEach(function (c) {
      var item = document.createElement('div');
      item.className = 'code-item ' + (c.status || 'pending');

      var statusChip = c.status === 'ok'
        ? '<span class="chip ok">اجرا شد</span>'
        : (c.status === 'error'
          ? '<span class="chip warn">خطا</span>'
          : '<span class="chip due">در انتظار</span>');

      var meta = c.ran
        ? 'آخرین اجرا ' + esc(c.ran_at) + ' · ' + fa(c.duration) + ' ثانیه · کد خروج ' + fa(c.exit_code)
        : 'حجم ' + fa(c.size) + ' · هنوز اجرا نشده';

      item.innerHTML =
        '<button class="play-btn" type="button" data-run="' + esc(c.name) + '" title="اجرای دوباره">' + SVG_PLAY + '</button>' +
        '<div class="code-main"><b>' + esc(c.name) + '</b><span>' + meta + '</span></div>' +
        '<div class="code-chips">' + statusChip + '</div>';
      list.appendChild(item);
    });
  }

  function renderShots(s) {
    var shots = s.shots || [];
    var key = JSON.stringify(shots);
    if (key === sig.shots) return;
    sig.shots = key;

    var grid = $('shots-grid');
    var empty = $('shots-empty');
    empty.classList.toggle('hidden', shots.length > 0);
    grid.innerHTML = '';

    shots.forEach(function (shot) {
      var card = document.createElement('div');
      card.className = 'shot';
      card.dataset.shot = shot.name;
      card.title = 'باز کردن ' + shot.name;
      card.innerHTML =
        '<img loading="lazy" src="' + esc(shot.url) + '" alt="' + esc(shot.name) + '">' +
        '<div><b>' + esc(shot.name) + '</b><span>' + fa(shot.size) + ' · ' + esc(shot.when) + '</span></div>';
      grid.appendChild(card);
    });
  }

  function scrollLogToEnd() {
    var box = $('log');
    box.scrollTop = box.scrollHeight;
  }

  function logClass(line) {
    if (/❌|⚠️|🗂|خطا/.test(line)) return 'err';
    if (/✅|📥|💾|📸|📋|🔊/.test(line)) return 'ok';
    if (/▶️|⚡|🔒|🆕/.test(line)) return 'act';
    return '';
  }

  function renderLog(s) {
    var logs = s.logs || [];
    var key = logs.length + '|' + (logs[logs.length - 1] || '') + '|' + (logs[0] || '');
    if (key === sig.log) return;
    sig.log = key;

    var box = $('log');
    var atEnd = box.scrollTop + box.clientHeight >= box.scrollHeight - 40;
    var html = '';

    logs.forEach(function (line) {
      var m = /^(\d{2}:\d{2}:\d{2})\s{1,2}([\s\S]*)$/.exec(line);
      var time = m ? m[1] : '';
      var text = m ? m[2] : line;
      html += '<div class="log-row ' + logClass(text) + '">' +
        (time ? '<time>' + fa(time) + '</time>' : '') +
        '<span>' + esc(text) + '</span></div>';
    });

    box.innerHTML = html;
    $('log-count').textContent = logs.length ? fa(logs.length) + ' خط' : '';
    if (atEnd) scrollLogToEnd();
  }

  var LAMPS = [
    ['internet', 'اینترنت'],
    ['drive', 'گوگل درایو'],
    ['collab', 'مخزن همکار']
  ];

  function renderStatus(s) {
    var status = s.status || {};
    var html = '';
    LAMPS.forEach(function (pair) {
      var info = status[pair[0]] || { state: 'wait', note: '…' };
      var cls = info.state === 'ok' ? 'ok' : (info.state === 'bad' ? 'bad' : '');
      html += '<span class="lamp ' + cls + '"><i></i>' + pair[1] +
        ' <b class="note">' + esc(info.note || '…') + '</b></span>';
    });
    $('lamps').innerHTML = html;

    $('status-mode').textContent = s.busy
      ? 'در حال کار: ' + s.busy
      : (s.auto ? 'حالت خودکار · هر ' + fa(s.auto_total) + ' ثانیه' : 'حالت دستی');
  }

  function renderRepo(s) {
    var collab = s.collab || {};
    var mother = s.mother || {};
    var line = (collab.owner || '—') + '/' + (collab.repo || '—') + ' @ ' + (collab.branch || '—');
    $('collab-current').textContent = 'فعلی: ' + line;
    $('collab-hint').textContent = collab.owner && collab.repo ? '' : 'اول مخزن را تنظیم و ذخیره کن.';
    $('mother-repo-code').textContent = (mother.owner || '—') + '/' + (mother.repo || '—') + ' @ ' + (mother.branch || '—');

    var key = line;
    if (key === sig.fields) return;
    sig.fields = key;
    if (collabDirty) return;

    var box = document.querySelector('[data-repo="collab"]');
    if (!box) return;
    ['owner', 'repo', 'branch'].forEach(function (field) {
      var input = box.querySelector('[data-field="' + field + '"]');
      if (input) input.value = collab[field] || '';
    });
  }

  function renderManage(s) {
    var mother = s.mother || {};
    var collab = s.collab || {};
    var status = s.status || {};
    var chips = [];

    chips.push(['accent', 'اینترنت: ' + ((status.internet || {}).note || '…')]);
    chips.push(['ok', 'درایو: ' + ((status.drive || {}).note || '…')]);
    chips.push(['due', 'اینجا فقط می‌خواند: ایجنت مادر']);
    chips.push(['ok', 'اینجا می‌خواند و می‌نویسد: ایجنت همکار']);

    var key = JSON.stringify(chips);
    if (key === sig.chips) return;
    sig.chips = key;

    $('manage-chips').innerHTML = chips.map(function (pair) {
      return '<span class="chip ' + pair[0] + '">' + esc(pair[1]) + '</span>';
    }).join('');

    $('manage-mother').textContent = (mother.owner || '—') + '/' + (mother.repo || '—');
    $('manage-collab').textContent = (collab.owner || '—') + '/' + (collab.repo || '—');
  }

  function renderEvents(events) {
    (events || []).forEach(function (ev) {
      if (!ev) return;
      if (ev.type === 'sound') play(ev.name);
      else if (ev.type === 'toast') toast(ev.text, ev.kind);
    });
  }

  /* ─────────────────────────────── توست ─────────────────────────────── */

  function toast(text, kind) {
    var wrap = $('toasts');
    var el = document.createElement('div');
    el.className = 'toast' + (kind === 'error' ? ' error' : '');
    el.textContent = text || '';
    wrap.appendChild(el);
    while (wrap.children.length > 4) wrap.removeChild(wrap.firstChild);
    setTimeout(function () {
      el.style.transition = 'opacity .3s, transform .3s';
      el.style.opacity = '0';
      el.style.transform = 'translateY(-8px)';
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 320);
    }, 2600);
  }

  /* ─────────────────────────────── پنجره تأیید ─────────────────────────────── */

  function openModal(info, action, arg) {
    pendingConfirm = { action: action, arg: arg };
    $('modal-title').textContent = info.title || 'تأیید';
    $('modal-text').textContent = info.message || '';
    $('modal').classList.remove('hidden');
    $('modal-yes').focus();
  }

  function closeModal() {
    $('modal').classList.add('hidden');
    pendingConfirm = null;
  }

  /* ─────────────────────────────── صدا زدن پایتون ─────────────────────────────── */

  function handleResult(res, action, arg) {
    if (!res) return;
    if (res.need_confirm) { openModal(res, action, arg); return; }
    if (res.state) res = res.state;
    if (res.version !== undefined) applyState(res);
  }

  function call(method, args) {
    var bridge = api();
    if (!bridge || typeof bridge[method] !== 'function') return Promise.resolve(null);
    return Promise.resolve(bridge[method].apply(bridge, args || [])).then(function (res) {
      return res;
    }).catch(function () { return null; });
  }

  /* اکشن‌های حساس: اول اجازه می‌گیرند، بعد با confirmed=true صدا زده می‌شوند */
  function act(action, arg) {
    var args = arg === undefined || arg === null ? [false] : [arg, false];
    call(action, args).then(function (res) { handleResult(res, action, arg); });
  }

  function actConfirmed(action, arg) {
    var args = arg === undefined || arg === null ? [true] : [arg, true];
    call(action, args).then(function (res) { handleResult(res, action, arg); });
  }

  /* ─────────────────────────────── رویدادها ─────────────────────────────── */

  function bind() {
    $('btn-check').addEventListener('click', function () { act('check_collab'); });
    $('btn-check-2').addEventListener('click', function () { act('check_collab'); });
    $('btn-run-new').addEventListener('click', function () { act('run_new'); });
    $('btn-shot').addEventListener('click', function () { act('take_screenshot'); });
    $('btn-report').addEventListener('click', function () { act('open_report'); });

    $('btn-open-codes').addEventListener('click', function () { call('open_path', ['codes']); });
    $('btn-open-shots').addEventListener('click', function () { call('open_path', ['shots']); });
    $('btn-rescan').addEventListener('click', function () {
      call('rescan_codes').then(function (res) { handleResult(res, 'rescan_codes', null); });
    });
    $('btn-clear-log').addEventListener('click', function () {
      call('clear_log').then(function (res) { handleResult(res, 'clear_log', null); });
    });

    $('auto-switch').addEventListener('change', function () {
      call('toggle_auto').then(function (res) { handleResult(res, 'toggle_auto', null); });
    });

    $('mute-btn').addEventListener('click', function () {
      var next = !(state && state.muted);
      if (state) state.muted = next;          /* تا پاسخ برسد، فوری عوض شود */
      $('mute-btn').classList.toggle('active', next);
      if (!next) play('toggle');
      call('set_muted', [next]).then(function (res) { handleResult(res, 'set_muted', null); });
    });

    $('theme-btn').addEventListener('click', function () {
      var next = state && state.theme === 'light' ? 'dark' : 'light';
      document.documentElement.dataset.theme = next;
      call('set_theme', [next]).then(function (res) { handleResult(res, 'set_theme', null); });
    });

    /* ذخیره‌ی مخزن همکار */
    Array.prototype.forEach.call(document.querySelectorAll('[data-save]'), function (btn) {
      btn.addEventListener('click', function () {
        var prefix = btn.dataset.save;
        var box = document.querySelector('[data-repo="' + prefix + '"]');
        if (!box) return;
        var values = ['owner', 'repo', 'branch'].map(function (field) {
          var input = box.querySelector('[data-field="' + field + '"]');
          return input ? input.value.trim() : '';
        });
        call('save_repo', [prefix, values[0], values[1], values[2]]).then(function (res) {
          collabDirty = false;
          sig.fields = '';
          handleResult(res, 'save_repo', null);
        });
      });
    });

    Array.prototype.forEach.call(document.querySelectorAll('[data-repo="collab"] input'), function (input) {
      input.addEventListener('input', function () { collabDirty = true; });
    });

    /* کتابخانه کدها */
    $('codes-list').addEventListener('click', function (event) {
      var btn = event.target.closest('[data-run]');
      if (!btn) return;
      act('run_single', btn.dataset.run);
    });

    /* اسکرین‌شات‌ها */
    $('shots-grid').addEventListener('click', function (event) {
      var card = event.target.closest('[data-shot]');
      if (!card) return;
      play('open');
      call('open_shot', [card.dataset.shot]);
    });

    /* میان‌بر پوشه‌ها */
    document.addEventListener('click', function (event) {
      var link = event.target.closest('[data-open]');
      if (link) call('open_path', [link.dataset.open]);
    });

    /* صدای کلیک */
    document.addEventListener('pointerdown', function (event) {
      if (event.target.closest('.btn, .tab, .icon-btn, .play-btn, .switch, .shot')) play('click');
    });

    /* پنجره تأیید */
    $('modal-yes').addEventListener('click', function () {
      var pending = pendingConfirm;
      closeModal();
      if (pending) actConfirmed(pending.action, pending.arg);
    });
    $('modal-no').addEventListener('click', closeModal);
    $('modal').addEventListener('click', function (event) {
      if (event.target === $('modal')) closeModal();
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') closeModal();
    });
  }

  /* ─────────────────────────────── تغییرات ─────────────────────────────── */

  function buildChangelog() {
    $('changelog').innerHTML = CHANGELOG.map(function (rel) {
      return '<div class="rel">' +
        '<h3>نسخه ' + rel.v + '</h3>' +
        '<time>' + rel.d + '</time>' +
        '<ul>' + rel.items.map(function (item) { return '<li>' + esc(item) + '</li>'; }).join('') + '</ul>' +
        '</div>';
    }).join('');
  }

  /* ─────────────────────────────── حلقه اصلی ─────────────────────────────── */

  var polling = false;

  function poll() {
    if (polling) return;
    polling = true;
    var bridge = api();
    if (!bridge) { polling = false; setTimeout(poll, 120); return; }
    Promise.resolve(bridge.get_state()).then(function (res) {
      polling = false;
      applyState(res);
      setTimeout(poll, POLL_MS);
    }).catch(function () {
      polling = false;
      setTimeout(poll, POLL_MS);
    });
  }

  var started = false;

  function start() {
    if (started) return;
    started = true;

    buildTabs();
    bind();
    buildChangelog();
    tickClock();
    setInterval(tickClock, 1000);

    /* صدای اولین کلیک کاربر (WebView تا کلیک اول صدا را پخش نمی‌کند) */
    var unlock = function () { document.removeEventListener('pointerdown', unlock); };
    document.addEventListener('pointerdown', unlock);

    setTimeout(poll, 60);
  }

  window.addEventListener('pywebviewready', start);

  document.addEventListener('DOMContentLoaded', function () {
    /* اگر پل پایتون دیرتر آماده شد، از این مسیر هم شروع می‌کنیم */
    setTimeout(function () { if (api()) start(); }, 220);
  });
})();
