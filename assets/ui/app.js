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
    { id: 'main', label: 'مغز ایجنت' },
    { id: 'mother', label: 'ایجنت مادر' },
    { id: 'collab', label: 'ایجنت همکار' },
    { id: 'manage', label: 'ایجنت مدیریت' },
    { id: 'bot', label: 'ربات تلگرام' },
    { id: 'codes', label: 'کتابخانه کدها' },
    { id: 'shots', label: 'اسکرین‌شات‌ها' },
    { id: 'live', label: 'گزارش زنده' },
    { id: 'changes', label: 'تغییرات' }
  ];

  var CHANGELOG = [
    {
      v: '۱.۷', d: '۱۴۰۵/۰۸/۰۲',
      items: [
        'تب تازه: «ربات تلگرام» با چهار زیرتب — تنظیمات، تست، صف پیام‌ها، راهنمای ایجنت همکار.',
        'ایجنت همکار می‌تواند از داخل کد پایتونش پیام در صف بگذارد؛ فوری یا زمان‌دار.',
        'صف با فاصله‌ی امن پیام‌ها را می‌فرستد و اگر تلگرام محدودیت داد، خودش صبر می‌کند.',
        'در «گزارش زنده» دکمه‌ی «کپی همه» اضافه شد.',
        'فاصله‌ی دور خودکار از خود صفحه قابل تغییر است (پیش‌فرض ۱۰ ثانیه).',
        'اگر گواهی امنیتی رد شود (فیلترشکن یا آنتی‌ویروس)، ارسال یک‌بار بدون بررسی گواهی تلاش می‌شود.',
        'امکان انتخاب و کپی آزادانه‌ی متن از تمام بخش‌های صفحه (از جمله داخل تب‌ها، زیرتب‌ها و دکمه‌ها).',
        'زمان‌بندی دقیق ربات تلگرام با فیلد scheduled_at (ISO 8601 با منطقه‌ی زمانی UTC و تهران) + تعریف صریح delay نسبت به لحظه ثبت + شمارش معکوس زنده و ویرایش پیام در صف.'
      ]
    },
    {
      v: '۱.۶', d: '۱۴۰۵/۰۸/۰۲',
      items: [
        'رابط کاربری از pygame به یک صفحه‌ی وب داخلی (pywebview) منتقل شد.',
        'کارت‌های گرد، فونت وزیرمتن و ظاهر تازه با همان هشت بخش.',
        'هشت تب کوچک در یک ردیف — همه با هم جا می‌شوند.',
        'حلقه‌ی شمارش معکوس نرم و پیوسته پر می‌شود، نه تیک‌تیک؛ سه ثانیه‌ی آخر هر ثانیه بوق.',
        'پنجره در حالت بزرگ (پرِ صفحه) باز می‌شود و اندازه‌اش قابل تغییر است.',
        'جدول شناسنامه‌ی ساخت کنار ساعت: نسخه، شناسه و تاریخ/ساعت آخرین کامیت.',
        'تم تاریک پیش‌فرض است؛ انتخاب کاربر بعد از آن ذخیره می‌شود.',
        'همه‌ی منطق قبلی دست‌نخورده ماند: بررسی مخزن، اجرای کدها، اسکرین‌شات، گزارش.'
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

  function pad2(n) { return String(n).padStart(2, '0'); }

  function fmtStamp(epoch) {
    if (!epoch) return '';
    var d = new Date(epoch * 1000);
    var j = g2j(d.getFullYear(), d.getMonth() + 1, d.getDate());
    return fa(j[0] + '/' + pad2(j[1]) + '/' + pad2(j[2])) + ' ' +
      fa(pad2(d.getHours()) + ':' + pad2(d.getMinutes()));
  }

  function setVal(id, value) {
    var el = $(id);
    if (el && document.activeElement !== el) el.value = value;
  }

  function copyText(text, label) {
    function done() { toast(label || 'کپی شد'); play('click'); }
    function fallback() {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      document.body.removeChild(ta);
      if (ok) done(); else toast('کپی ممکن نشد', 'error');
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(fallback);
    } else {
      fallback();
    }
  }

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
  var botDirty = false;
  var sig = { codes: '', shots: '', log: '', paths: '', chips: '', fields: '', queue: '' };
  var pendingConfirm = null;

  function api() {
    return (window.pywebview && window.pywebview.api) || null;
  }

  /* ─────────────────────────────── تب‌ها ─────────────────────────────── */

  function buildTabs() {
    var box = $('tabs-row-1');
    TABS.forEach(function (tab) {
      var btn = document.createElement('button');
      btn.className = 'tab';
      btn.type = 'button';
      btn.dataset.tab = tab.id;
      btn.textContent = tab.label;
      btn.title = tab.label;
      btn.addEventListener('click', function () { setTab(tab.id); });
      box.appendChild(btn);
    });
    var saved = null;
    try { saved = localStorage.getItem('wa.tab'); } catch (e) { }
    var ok = TABS.some(function (t) { return t.id === saved; });
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

  function fmtCountdown(remSec) {
    var s = Math.ceil(remSec);
    if (s <= 0) return '⚡ در نوبت ارسال';
    if (s < 60) return '⏳ ' + fa(s) + ' ثانیه دیگر';
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    if (h > 0) {
      return '⏳ ' + fa(h) + ' ساعت و ' + fa(m) + ' دقیقه و ' + fa(sec) + ' ثانیه دیگر';
    }
    return '⏳ ' + fa(m) + ' دقیقه و ' + fa(sec) + ' ثانیه دیگر';
  }

  function updateQueueCountdowns() {
    var nowSec = Date.now() / 1000;
    Array.prototype.forEach.call(document.querySelectorAll('.q-countdown[data-send-at]'), function (el) {
      var target = parseFloat(el.dataset.sendAt || '0');
      if (!target) {
        el.textContent = '⚡ در نوبت ارسال';
        return;
      }
      el.textContent = fmtCountdown(target - nowSec);
    });
  }

  function tickClock() {
    var now = new Date();
    var hh = String(now.getHours()).padStart(2, '0');
    var mm = String(now.getMinutes()).padStart(2, '0');
    var ss = String(now.getSeconds()).padStart(2, '0');
    $('clock').textContent = fa(hh + ':' + mm + ':' + ss);
    var j = g2j(now.getFullYear(), now.getMonth() + 1, now.getDate());
    var wd = WEEKDAYS[(now.getDay() + 1) % 7];
    $('date').textContent = wd + ' ' + fa(j[2]) + ' ' + MONTHS[j[1] - 1] + ' ' + fa(j[0]);
    updateQueueCountdowns();
  }

  /* ─────────────────────────────── رندر ─────────────────────────────── */

  function applyState(s) {
    if (!s || s.version === undefined) return;
    state = s;

    document.documentElement.dataset.theme = s.theme === 'light' ? 'light' : 'dark';

    $('version').textContent = s.version_fa || fa(s.version);
    $('build').textContent = s.build || '—';
    $('build-date').textContent = s.build_date || '—';
    $('build-time').textContent = s.build_time || '—';
    $('build-table').title =
      'شناسنامه‌ی ساخت' + (s.build_subject ? '\n' + s.build_subject : '') +
      (s.build_source ? '\nمنبع: ' + s.build_source : '');

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
    renderBot(s);
    renderEvents(s.events);
  }

  function renderMode(s) {
    var num = $('ring-number');
    var label = $('ring-label');
    var title = $('mode-title');
    var hint = $('mode-hint');
    var sw = $('auto-switch');

    sw.checked = !!s.auto;
    setVal('sync-seconds', s.auto_total || 10);
    document.body.classList.toggle('busy', !!s.busy);

    if (s.busy) {
      title.textContent = 'در حال کار';
      title.classList.add('on');
      hint.textContent = s.busy;
      num.textContent = '…';
      label.textContent = 'صبر کن';
      ringState = { mode: 'busy', remaining: 0, total: 0, receivedAt: performance.now() };
    } else if (s.auto) {
      title.textContent = 'خودکار';
      title.classList.add('on');
      hint.textContent = 'هر ' + fa(s.auto_total) + ' ثانیه مخزن همکار بررسی می‌شود؛ بدون پرسیدن.';
      label.textContent = 'تا دور بعد';
      ringState = {
        mode: 'auto',
        remaining: Number(s.auto_remaining) || 0,
        total: Number(s.auto_total) || 10,
        receivedAt: performance.now()
      };
    } else {
      title.textContent = 'دستی';
      title.classList.remove('on');
      hint.textContent = 'هیچ کاری بدون اجازه‌ی تو انجام نمی‌شود.';
      num.textContent = '—';
      label.textContent = 'دستی';
      ringState = { mode: 'manual', remaining: 0, total: 0, receivedAt: performance.now() };
      $('ring').classList.remove('warn');
    }
  }

  /* حلقه‌ی شمارش معکوس: هر فریم (۶۰ بار در ثانیه) کشیده می‌شود، نه پرشی */
  var CIRC = 2 * Math.PI * 42;
  var ringState = { mode: 'manual', remaining: 0, total: 10, receivedAt: 0 };
  var lastTickSec = null;

  function animateRing(ts) {
    var el = $('ring');
    var fraction = 0;

    if (ringState.mode === 'auto') {
      var elapsed = (ts - ringState.receivedAt) / 1000;
      var rem = Math.max(0, ringState.remaining - elapsed);
      fraction = ringState.total ? Math.min(1, Math.max(0, 1 - rem / ringState.total)) : 0;

      var secs = Math.ceil(rem);
      if ($('ring-number').textContent !== fa(secs)) $('ring-number').textContent = fa(secs);

      /* سه ثانیه‌ی آخر: هر ثانیه یک بوق */
      if (secs !== lastTickSec) {
        if (secs > 0 && secs <= 3) play('tick');
        lastTickSec = secs;
      }
      el.classList.toggle('warn', rem <= 3);
    } else if (ringState.mode === 'busy') {
      fraction = 0.35;
    }

    el.style.strokeDashoffset = String(CIRC * (1 - fraction));
    requestAnimationFrame(animateRing);
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

  /* ─────────────────────────── ربات تلگرام ─────────────────────────── */

  function renderBot(s) {
    var bot = s.bot || {};
    var q = bot.queue || [];
    var counts = bot.counts || { pending: 0, sent: 0, failed: 0 };

    if (!botDirty) {
      setVal('bot-token', bot.token || '');
      setVal('bot-chat', bot.chat_id || '');
      setVal('bot-gap', bot.gap !== undefined ? bot.gap : 1);
      setVal('bot-missed-policy', bot.missed_policy || 'send');
      $('bot-enabled').checked = !!bot.enabled;
    }

    var tzBadge = $('bot-tz-badge');
    if (tzBadge) {
      var tehClock = (bot.now_tehran || '').slice(11, 19);
      tzBadge.textContent = 'منطقه زمانی: تهران (UTC+03:30)' + (tehClock ? ' · اکنون ' + fa(tehClock) : '');
    }

    var title = $('bot-enabled-title');
    title.textContent = bot.enabled ? 'ربات روشن است' : 'ربات خاموش است';
    title.classList.toggle('on', !!bot.enabled);
    $('bot-enabled-hint').textContent = bot.enabled
      ? 'پیام‌های سررسیدشده به ترتیب زمان مقرر (با دقت زیر ۱ ثانیه) فرستاده می‌شوند.'
      : 'پیام‌ها روی دیسک در صف می‌مانند تا ربات را روشن کنی.';

    var meEl = $('bot-me');
    if (bot.me && bot.me.username) {
      meEl.textContent = 'ربات: @' + bot.me.username;
      meEl.className = 'small ok-text';
    } else if (bot.token && !bot.token_shape_ok) {
      meEl.textContent = 'شکل توکن درست نیست';
      meEl.className = 'small err-text';
    } else if (bot.token) {
      meEl.textContent = 'توکن ذخیره شده — «بررسی توکن» را بزن';
      meEl.className = 'small muted';
    } else {
      meEl.textContent = 'توکنی ذخیره نشده';
      meEl.className = 'small muted';
    }

    $('bot-api-file').textContent = bot.api_file || '—';
    $('guide-api-file').textContent = (bot.api_file || '—') + ' — پورت ' + fa(bot.api_port || '—');

    $('bot-counts').textContent =
      'در انتظار: ' + fa(counts.pending) +
      ' · فرستاده: ' + fa(counts.sent) +
      ' · ناموفق: ' + fa(counts.failed);

    var badge = $('bot-tab-count');
    if (counts.pending) {
      badge.textContent = fa(counts.pending);
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }

    var tested = bot.last_test;
    var resEl = $('bot-test-result');
    if (tested) {
      resEl.textContent = (tested.ok ? '✅ ' : '❌ ') + tested.detail + ' · ' + fa(tested.at || '');
      resEl.className = 'small ' + (tested.ok ? 'ok-text' : 'err-text');
    } else {
      resEl.textContent = '';
    }

    renderQueue(q);
    updateQueueCountdowns();
  }

  function queueItemHtml(item) {
    var status = item.status || 'pending';
    var label = status === 'sent' ? 'فرستاده شد' : (status === 'failed' ? 'ناموفق' : 'در صف');
    var mode = item.mode || (item.send_at ? 'delay' : 'immediate');
    var modeLabel = mode === 'scheduled_at' ? 'ساعت دقیق' : (mode === 'delay' ? 'با تأخیر' : 'فوری');

    var targetStr = item.send_at_jalali
      ? fa(item.send_at_jalali) + ' تهران'
      : (item.send_at ? fmtStamp(item.send_at) : 'همین حالا');
    var utcStr = item.scheduled_at_utc ? item.scheduled_at_utc.slice(11, 19) + ' UTC' : '';

    var meta = [
      '<span class="chip-line">' + label + ' (' + modeLabel + ')</span>',
      '<span>ثبت: ' + (item.created ? fmtStamp(item.created) : '—') + '</span>',
      '<span>موعد ارسال: <b>' + esc(targetStr) + '</b>' + (utcStr ? ' (' + esc(utcStr) + ')' : '') + '</span>',
      '<span>' + esc(item.source === 'api' ? 'از کد ایجنت همکار' : 'از پنل') + '</span>'
    ];
    if (status === 'pending') {
      meta.push('<span class="q-countdown" data-send-at="' + esc(item.send_at || 0) + '">…</span>');
    }
    if (status === 'sent' && item.sent_at) {
      meta.push('<span>ارسال واقعی: ' + fmtStamp(item.sent_at) + '</span>');
    }
    if (item.error) {
      meta.push('<span class="err">' + esc(item.error) + '</span>');
    }

    var actions = '';
    if (status === 'pending') {
      actions += '<button class="btn btn-ghost" type="button" data-qnow="' + esc(item.id) + '">ارسال فوری</button>';
      actions += '<button class="btn btn-ghost" type="button" data-qedit="' + esc(item.id) + '">ویرایش</button>';
    }
    actions += '<button class="btn btn-danger" type="button" data-qdel="' + esc(item.id) + '">حذف</button>';

    return '<div class="queue-item ' + esc(status) + '" data-item-id="' + esc(item.id) + '">' +
      '<div class="q-main"><p>' + esc(item.text) + '</p>' +
      '<div class="q-meta">' + meta.join('') + '</div></div>' +
      '<div class="q-actions">' + actions + '</div>' +
      '</div>';
  }

  function renderQueue(items) {
    var list = $('bot-list');
    var empty = $('bot-empty');
    if (!list) return;
    empty.classList.toggle('hidden', items.length > 0);

    var signature = JSON.stringify(items);
    if (signature === sig.queue) return;
    sig.queue = signature;

    /* پیام‌های در انتظار بر اساس زمان ارسال، و بقیه از جدید به قدیم */
    var pending = items.filter(function (i) { return i.status === 'pending'; })
      .sort(function (a, b) { return (a.send_at || 0) - (b.send_at || 0); });
    var others = items.filter(function (i) { return i.status !== 'pending'; }).reverse();
    var ordered = pending.concat(others);
    list.innerHTML = ordered.map(queueItemHtml).join('');
  }

  function saveBotSettings() {
    var token = $('bot-token').value.trim();
    var chat = $('bot-chat').value.trim();
    var gap = $('bot-gap').value.trim() || '1';
    var policy = $('bot-missed-policy') ? $('bot-missed-policy').value : 'send';
    var enabled = $('bot-enabled').checked;
    botDirty = false;
    call('save_bot', [token, chat, enabled, gap, policy]).then(function (res) {
      handleResult(res, 'save_bot', null);
    });
  }

  function setBotSub(name) {
    Array.prototype.forEach.call(document.querySelectorAll('#bot-subtabs .subtab'), function (b) {
      b.classList.toggle('active', b.dataset.sub === name);
    });
    Array.prototype.forEach.call(document.querySelectorAll('.view[data-tab="bot"] .subview'), function (v) {
      v.classList.toggle('active', v.dataset.sub === name);
    });
    try { localStorage.setItem('wa.botsub', name); } catch (e) { }
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
  function actArgs(action, arg, confirmed) {
    if (action === 'bot_send_test') return [arg.text, arg.chat_id, confirmed];
    if (arg === undefined || arg === null) return [confirmed];
    return [arg, confirmed];
  }

  function act(action, arg) {
    call(action, actArgs(action, arg, false)).then(function (res) {
      handleResult(res, action, arg);
    });
  }

  function actConfirmed(action, arg) {
    call(action, actArgs(action, arg, true)).then(function (res) {
      handleResult(res, action, arg);
    });
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

    function applySyncSeconds() {
      var input = $('sync-seconds');
      var value = Math.max(3, Math.min(600, parseInt(input.value, 10) || 10));
      input.value = value;
      call('set_sync_seconds', [value]).then(function (res) {
        handleResult(res, 'set_sync_seconds', null);
      });
    }

    $('sync-seconds').addEventListener('change', applySyncSeconds);
    $('sync-seconds').addEventListener('keydown', function (event) {
      if (event.key === 'Enter') { event.preventDefault(); applySyncSeconds(); }
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

    /* ── ربات تلگرام ── */
    Array.prototype.forEach.call(document.querySelectorAll('#bot-subtabs .subtab'), function (btn) {
      btn.addEventListener('click', function () { setBotSub(btn.dataset.sub); });
    });

    Array.prototype.forEach.call(document.querySelectorAll('[data-bot-field]'), function (input) {
      input.addEventListener('input', function () { botDirty = true; });
    });

    $('bot-enabled').addEventListener('change', function () {
      botDirty = false;
      saveBotSettings();
    });

    $('bot-save').addEventListener('click', saveBotSettings);

    $('bot-check').addEventListener('click', function () {
      if (botDirty) { toast('اول دکمه‌ی ذخیره را بزن', 'error'); return; }
      call('bot_check_token').then(function (res) { handleResult(res, 'bot_check_token', null); });
    });

    $('bot-test-send').addEventListener('click', function () {
      if (botDirty) { toast('اول دکمه‌ی ذخیره را بزن', 'error'); return; }
      act('bot_send_test', {
        text: $('bot-test-text').value.trim(),
        chat_id: $('bot-test-chat').value.trim()
      });
    });

    function updateScheduleInputs() {
      var mode = $('bot-msg-mode').value;
      $('bot-clock-wrap').classList.toggle('hidden', mode !== 'clock');
      $('bot-delay-wrap').classList.toggle('hidden', mode !== 'delay');
      if (mode === 'clock' && !$('bot-msg-clock').value) {
        var d = new Date(Date.now() + 120000);
        $('bot-msg-clock').value =
          pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
      }
    }

    $('bot-msg-mode').addEventListener('change', updateScheduleInputs);

    $('bot-add').addEventListener('click', function () {
      var text = $('bot-text').value.trim();
      if (!text) { toast('متن پیام خالی است', 'error'); return; }
      var chat = $('bot-msg-chat').value.trim();
      var mode = $('bot-msg-mode').value;
      var delay = null;
      var scheduledAt = null;

      if (mode === 'clock') {
        scheduledAt = $('bot-msg-clock').value.trim();
        if (!scheduledAt) { toast('ساعت دقیق ارسال را وارد کن', 'error'); return; }
      } else if (mode === 'delay') {
        delay = Number($('bot-msg-delay').value || 0);
        if (delay < 0) { toast('تأخیر نمی‌تواند منفی باشد', 'error'); return; }
      } else {
        delay = 0;
      }

      call('bot_add', [text, chat, delay, scheduledAt]).then(function (res) {
        $('bot-text').value = '';
        handleResult(res, 'bot_add', null);
      });
    });

    $('bot-clear').addEventListener('click', function () {
      call('bot_clear_queue', [true]).then(function (res) {
        handleResult(res, 'bot_clear_queue', null);
      });
    });

    $('bot-edit-cancel').addEventListener('click', function () {
      $('bot-edit-card').classList.add('hidden');
    });

    $('bot-edit-save').addEventListener('click', function () {
      var id = $('bot-edit-id').textContent.trim();
      var text = $('bot-edit-text').value.trim();
      var clockStr = $('bot-edit-clock').value.trim();
      var delayRaw = $('bot-edit-delay').value.trim();
      if (!text) { toast('متن پیام خالی است', 'error'); return; }
      if (clockStr && delayRaw) {
        toast('فقط یکی از ساعت دقیق یا تأخیر را پر کن', 'error');
        return;
      }
      var delayVal = delayRaw !== '' ? Number(delayRaw) : null;
      call('bot_edit_ui', [id, text, clockStr, delayVal]).then(function (res) {
        $('bot-edit-card').classList.add('hidden');
        handleResult(res, 'bot_edit_ui', null);
      });
    });

    $('bot-list').addEventListener('click', function (event) {
      var nowBtn = event.target.closest('[data-qnow]');
      if (nowBtn) {
        call('bot_set_send_at', [nowBtn.dataset.qnow]).then(function (res) {
          handleResult(res, 'bot_set_send_at', null);
        });
        return;
      }
      var editBtn = event.target.closest('[data-qedit]');
      if (editBtn) {
        var itemId = editBtn.dataset.qedit;
        var q = (state && state.bot && state.bot.queue) || [];
        var found = q.filter(function (x) { return x.id === itemId; })[0];
        if (!found) return;
        $('bot-edit-id').textContent = found.id;
        $('bot-edit-text').value = found.text || '';
        $('bot-edit-clock').value = found.scheduled_at_tehran || '';
        $('bot-edit-delay').value = '';
        $('bot-edit-card').classList.remove('hidden');
        $('bot-edit-text').focus();
        return;
      }
      var delBtn = event.target.closest('[data-qdel]');
      if (delBtn) {
        call('bot_remove', [delBtn.dataset.qdel]).then(function (res) {
          handleResult(res, 'bot_remove', null);
        });
      }
    });

    /* کپی گزارش و کپی کد راهنما */
    $('btn-copy-log').addEventListener('click', function () {
      var lines = (state && state.logs) || [];
      if (!lines.length) { toast('گزارشی برای کپی نیست', 'error'); return; }
      copyText(lines.join('\n'), 'گزارش کپی شد');
    });

    $('copy-guide').addEventListener('click', function () {
      copyText($('guide-code').textContent, 'کد کپی شد');
    });

    $('copy-guide-all').addEventListener('click', function () {
      copyText($('guide-full-card').innerText, 'کل راهنما کپی شد');
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

    var savedSub = null;
    try { savedSub = localStorage.getItem('wa.botsub'); } catch (e) { }
    setBotSub(savedSub === 'test' || savedSub === 'queue' || savedSub === 'guide' ? savedSub : 'settings');
    tickClock();
    setInterval(tickClock, 1000);
    requestAnimationFrame(animateRing);

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
