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
      v: '۱.۷-۲۰', d: '۱۴۰۵/۰۸/۰۸',
      items: [
        'کنترل اضطراری توقف همه از Heartbeat مستقل، با Idempotency و گزارش نتیجه‌ی تأییدشده به مدیریت.',
        'Registry و PIDهای متعلق پس از توقف دوباره بررسی می‌شوند؛ شکست توقف با شناسه‌ها و PIDهای باقی‌مانده گزارش می‌شود.',
        'نسخه و Commit جاری از Git HEAD یا build stamp زمان اجرای run.bat خوانده می‌شوند.'
      ]
    },
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
        'زمان‌بندی دقیق ربات تلگرام با فیلد scheduled_at (ISO 8601 با منطقه‌ی زمانی UTC و تهران) + تعریف صریح delay نسبت به لحظه ثبت + شمارش معکوس زنده و ویرایش پیام در صف.',
        'ماژول مستقل manager_client.py با رمزنگاری ویندوز DPAPI (manager_secret.bin)، ارسال خودکار Heartbeat هر ۳۰ ثانیه و پاسخ خودکار «سلام ایجنت مدیریت.» به تست اتصال D1 هر ۵ ثانیه.'
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
  var mgrDirty = false;
  var localCancelSubmitting = false;
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
    renderExecutionCenter((s.manager && s.manager.executions) || [], (s.manager && s.manager.emergency_control_status) || "");
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

  var EXECUTION_STATUS_LABELS = {
    preparing: 'در حال آماده‌سازی', waiting_confirmation: 'در انتظار تأیید کاربر', running: 'در حال اجرا',
    monitoring: 'پایش پس‌زمینه فعال', stopping: 'در حال توقف Processها', cancelled: 'متوقف شد',
    succeeded: 'با موفقیت پایان یافت', failed: 'ناموفق', timed_out: 'پایان زمان مجاز',
    rejected: 'ردشده توسط کاربر', termination_failed: 'توقف ناموفق؛ بررسی دستی لازم است'
  };
  var EXECUTION_TERMINAL = ['cancelled', 'succeeded', 'failed', 'timed_out', 'rejected', 'termination_failed'];

  function tehranJalaliStamp(iso) {
    if (!iso) return '—';
    var value = new Date(iso);
    if (isNaN(value.getTime())) return '—';
    var t = new Date(value.getTime() + (3.5 * 60 * 60 * 1000));
    var j = g2j(t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate());
    return fa(j[0] + '/' + pad2(j[1]) + '/' + pad2(j[2]) + ' ' + pad2(t.getUTCHours()) + ':' + pad2(t.getUTCMinutes()) + ':' + pad2(t.getUTCSeconds()));
  }

  function executionDuration(row) {
    var start = new Date(row.started_at || row.updated_at || '').getTime();
    if (!start || isNaN(start)) return '—';
    var end = row.completed_at ? new Date(row.completed_at).getTime() : Date.now();
    var seconds = Math.max(0, Math.floor((end - start) / 1000));
    var min = Math.floor(seconds / 60), sec = seconds % 60;
    return min ? fa(min + ' دقیقه ' + sec + ' ثانیه') : fa(sec + ' ثانیه');
  }

  function renderExecutionCenter(rows, emergencyStatus) {
    var box = $('execution-groups');
    if (!box) return;
    var controlStatus = $('execution-control-status');
    if (controlStatus) {
      controlStatus.textContent = emergencyStatus || '';
      controlStatus.classList.toggle('visible', !!emergencyStatus);
      controlStatus.dataset.state = /ناموفق|نشد|خطا/.test(emergencyStatus || '') ? 'error' : (/در حال/.test(emergencyStatus || '') || /دریافت شد/.test(emergencyStatus || '') ? 'active' : 'success');
    }
    rows = Array.isArray(rows) ? rows : [];
    var activeStatuses = ['preparing', 'waiting_confirmation', 'running', 'monitoring'];
    var active = rows.filter(function (r) { return EXECUTION_TERMINAL.indexOf(r.status) < 0 && r.status !== 'stopping'; });
    var stopping = rows.filter(function (r) { return r.status === 'stopping'; });
    var finished = rows.filter(function (r) { return EXECUTION_TERMINAL.indexOf(r.status) >= 0; });
    var runningCount = rows.filter(function (r) { return r.status === 'running'; }).length;
    var preparingCount = rows.filter(function (r) { return r.status === 'preparing' || r.status === 'waiting_confirmation' || r.status === 'monitoring'; }).length;
    var finishedCount = finished.length;
    var counters = $('execution-counters');
    if (counters) counters.innerHTML = [
      ['running', runningCount, 'در حال اجرا'], ['preparing', preparingCount, 'در حال آماده‌سازی'],
      ['stopping', stopping.length, 'در حال توقف'], ['finished', finishedCount, 'پایان‌یافته']
    ].map(function (x) { return '<div class="execution-counter ' + x[0] + '"><strong>' + fa(x[1]) + '</strong><span>' + x[2] + '</span></div>'; }).join('');

    function rowHtml(r) {
      var id = String(r.execution_id || r.command_id || '');
      var status = String(r.status || 'preparing');
      var label = EXECUTION_STATUS_LABELS[status] || 'در حال آماده‌سازی';
      var pids = Array.isArray(r.child_pids) ? r.child_pids : [];
      var pidText = r.pid ? ('Process اصلی PID ' + fa(r.pid) + ' · والد Agent PID ' + fa(r.parent_pid || '—') + ' · فرزندها: ' + (pids.length ? pids.map(function (p) { return fa(p); }).join(', ') : '—')) : 'Process هنوز شروع نشده';
      var mode = r.execution_mode === 'background' ? 'پس‌زمینه' : 'foreground';
      var cmd = r.command_id ? String(r.command_id) : id;
      var shortCmd = cmd.length > 24 ? cmd.slice(0, 21) + '…' : cmd;
      var meta = [esc(String(r.source || 'فرمان مدیریتی')), esc(shortCmd), esc(mode), esc(pidText),
        'شروع: ' + esc(tehranJalaliStamp(r.started_at)), 'مدت: ' + esc(executionDuration(r)), 'مرحله: ' + esc(String(r.stage || '—'))].join(' · ');
      var button = activeStatuses.indexOf(status) >= 0 || status === 'stopping'
        ? '<div class="execution-row-actions"><button class="btn danger execution-stop-one" data-execution-stop="' + esc(id) + '" type="button" ' + (status === 'stopping' ? 'disabled' : '') + '>' + (status === 'stopping' ? 'در حال توقف…' : 'توقف فوری این اجرا') + '</button></div>' : '';
      return '<article class="execution-row" data-status="' + esc(status) + '"><div class="execution-row-head"><span class="execution-row-title">' + esc(r.title || r.job_name || 'اجرای ایجنت') + '</span><span class="execution-row-state">' + esc(label) + '</span></div>' +
        '<div class="execution-row-meta">' + meta + '</div>' +
        (r.last_message ? '<div class="execution-row-message">' + esc(r.last_message) + '</div>' : '') +
        (r.error_summary ? '<div class="execution-row-message execution-row-error">' + esc(r.error_summary) + '</div>' : '') + button + '</article>';
    }
    function group(title, values) {
      if (!values.length) return '';
      return '<section class="execution-group"><h3 class="execution-group-title">' + title + ' · ' + fa(values.length) + '</h3>' + values.map(rowHtml).join('') + '</section>';
    }
    if (!rows.length) {
      box.innerHTML = '<div class="execution-empty"><strong>اجرای فعالی وجود ندارد</strong><span>فرمان‌های دریافت‌شده از مدیریت و پایش‌های پس‌زمینه در این بخش نمایش داده می‌شوند.</span></div>';
      return;
    }
    box.innerHTML = group('فعال', active) + group('در حال توقف', stopping) + group('اخیراً پایان‌یافته', finished);
  }

  function renderMode(s) {
    var card = $('brain-mode-card');
    var title = $('mode-title');
    var hint = $('mode-hint');
    var toggle = $('auto-switch');
    var stateLabel = $('mode-state-label');
    var automatic = !!s.auto;

    toggle.checked = automatic;
    document.body.classList.toggle('busy', !!s.busy);
    card.classList.toggle('is-auto', automatic);

    if (s.busy) {
      title.textContent = 'در حال اجرا';
      hint.textContent = s.busy;
    } else if (automatic) {
      title.textContent = 'خودکار';
      hint.textContent = 'فرمان‌های مجاز ایجنت مدیریت بدون تأیید محلی اجرا می‌شوند؛ دور خودکار برنامه هم فعال است.';
    } else {
      title.textContent = 'دستی';
      hint.textContent = 'فرمان‌های ایجنت مدیریت پیش از اجرا تأیید محلی می‌گیرند.';
    }
    stateLabel.textContent = automatic ? 'اجرا بدون تأیید محلی' : 'تأیید محلی روشن است';
  }

  function renderStats(s) {
    var codes = s.codes || [];
    var done = codes.filter(function (c) { return c.ran; }).length;
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
    ['collab', 'مخزن همکار'],
    ['manager', 'ایجنت مدیریت']
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
      : (s.auto ? 'حالت خودکار · بدون تأیید محلی' : 'حالت دستی · تأیید محلی لازم است');
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
    var mgr = s.manager || {};
    var chips = [];

    var mgrNote = mgr.note || ((status.manager || {}).note || 'در انتظار کلید');
    var mgrBadge = $('mgr-status-badge');
    if (mgrBadge) {
      mgrBadge.textContent = mgr.connected ? ('وصل · ' + mgrNote) : mgrNote;
      mgrBadge.className = 'chip ' + (mgr.connected ? 'ok' : (mgrNote === 'کلید نامعتبر' || mgrNote === 'دسترسی ناکافی' ? 'bad' : 'due'));
    }

    var cancelButton = $('mgr-cancel-local');
    var cancelStatus = $('mgr-cancel-status');
    var activeCommand = !!mgr.active_command_id;
    if (!activeCommand) localCancelSubmitting = false;
    var cancelPending = activeCommand && (!!mgr.local_cancel_requested || localCancelSubmitting);
    if (cancelButton) {
      cancelButton.disabled = !activeCommand || cancelPending;
      cancelButton.textContent = cancelPending ? 'در حال توقف…' : 'توقف فوری اجرای فعال';
    }
    if (cancelStatus) {
      cancelStatus.textContent = !activeCommand ? 'فرمان فعالی نیست'
        : (cancelPending ? 'درخواست لغو محلی ثبت شد' : 'فقط هنگام اجرای فرمان فعال است');
    }

    if (!mgrDirty && mgr.base_url) {
      setVal('mgr-base-url', mgr.base_url);
    }

    var kp = $('mgr-key-prefix');
    if (kp) kp.textContent = mgr.configured && mgr.key_prefix ? mgr.key_prefix : 'ثبت نشده';

    var hb = $('mgr-last-hb');
    if (hb) hb.textContent = mgr.last_heartbeat_at ? fa(mgr.last_heartbeat_at) : (mgr.last_error ? ('خطا: ' + mgr.last_error) : '—');

    var lt = $('mgr-last-test');
    if (lt) {
      if (mgr.last_test_at) {
        lt.textContent = fa(mgr.last_test_at) + ' · شناسه: ' + (mgr.last_test_id || '—') + ' · پاسخ: «' + (mgr.last_test_reply || 'سلام ایجنت مدیریت.') + '»';
      } else {
        lt.textContent = 'هنوز تستی دریافت نشده (پاسخ خودکار: «سلام ایجنت مدیریت.»)';
      }
    }

    var sp = $('mgr-secret-path');
    if (sp && mgr.secret_file) sp.textContent = mgr.secret_file;

    chips.push(['accent', 'اینترنت: ' + ((status.internet || {}).note || '…')]);
    chips.push(['ok', 'درایو: ' + ((status.drive || {}).note || '…')]);
    chips.push([mgr.connected ? 'ok' : 'due', 'ایجنت مدیریت: ' + mgrNote]);
    chips.push(['due', 'ایجنت مادر: فقط خواندن']);
    chips.push(['ok', 'ایجنت همکار: خواندن و نوشتن']);

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
    $('btn-check-2').addEventListener('click', function () { act('check_collab'); });
    $('btn-run-new').addEventListener('click', function () { act('run_new'); });
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

    $('execution-stop-all').addEventListener('click', function () {
      openModal({title: 'توقف همه اجراهای ایجنت', message: 'همه اجراهای فعال و پایش‌های پس‌زمینه متعلق به Windows Agent متوقف شوند؟ این عملیات برنامه‌های نامرتبط ویندوز را نمی‌بندد.'}, 'manager_stop_all_executions', null);
    });
    $('execution-groups').addEventListener('click', function (event) {
      var button = event.target.closest('[data-execution-stop]');
      if (!button || button.disabled) return;
      openModal({title: 'توقف فوری این اجرا', message: 'این اجرا و تمام Processهای فرزند متعلق به آن متوقف شوند؟ برنامه‌های نامرتبط ویندوز بسته نمی‌شوند.'}, 'manager_stop_execution', button.dataset.executionStop);
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

    /* ایجنت مدیریت (manager_client.py + DPAPI) */
    $('mgr-base-url').addEventListener('input', function () { mgrDirty = true; });
    $('mgr-agent-key').addEventListener('input', function () { mgrDirty = true; });

    $('mgr-toggle-key').addEventListener('click', function () {
      var input = $('mgr-agent-key');
      input.type = input.type === 'password' ? 'text' : 'password';
    });

    $('mgr-save').addEventListener('click', function () {
      var baseUrl = $('mgr-base-url').value.trim();
      var keyOrJson = $('mgr-agent-key').value.trim();
      call('manager_save_config', [baseUrl, keyOrJson]).then(function (res) {
        mgrDirty = false;
        $('mgr-agent-key').value = '';
        handleResult(res, 'manager_save_config', null);
      });
    });

    $('mgr-sync').addEventListener('click', function () {
      call('manager_sync_now').then(function (res) {
        handleResult(res, 'manager_sync_now', null);
      });
    });

    $('mgr-cancel-local').addEventListener('click', function () {
      if (localCancelSubmitting || $('mgr-cancel-local').disabled) return;
      if (!window.confirm('فرمان فعال متوقف می‌شود. آیا ادامه می‌دهی؟')) return;
      localCancelSubmitting = true;
      $('mgr-cancel-local').disabled = true;
      $('mgr-cancel-local').textContent = 'در حال توقف…';
      $('mgr-cancel-status').textContent = 'درخواست لغو محلی…';
      call('manager_cancel_local').then(function (res) {
        var manager = res && res.state && res.state.manager;
        if (!manager || !manager.local_cancel_requested || !manager.active_command_id) {
          localCancelSubmitting = false;
        }
        if (res && res.ok === false) {
          $('mgr-cancel-status').textContent = 'فرمان فعالی برای لغو نیست';
        }
        handleResult(res, 'manager_cancel_local', null);
      });
    });

    $('mgr-clear').addEventListener('click', function () {
      call('manager_clear_config').then(function (res) {
        mgrDirty = false;
        $('mgr-agent-key').value = '';
        handleResult(res, 'manager_clear_config', null);
      });
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
