/**
 * PrintEdge shared frontend utilities
 */
(function (global) {
  'use strict';

  const Toast = {
    container: null,

    ensureContainer() {
      if (!this.container) {
        this.container = document.createElement('div');
        this.container.id = 'toast-container';
        this.container.className =
          'fixed top-20 right-4 z-[200] flex flex-col gap-3 pointer-events-none w-full max-w-sm px-4 md:px-0';
        document.body.appendChild(this.container);
      }
      return this.container;
    },

    show(message, type = 'info', duration = 5000) {
      const container = this.ensureContainer();
      const typeMap = {
        success: { border: 'var(--pe-status-success, #059669)', bg: 'var(--pe-color-surface, #ffffff)', icon: 'bi-check-lg', iconColor: 'var(--pe-status-success, #059669)' },
        error: { border: 'var(--pe-status-danger, #dc2626)', bg: 'var(--pe-color-surface, #ffffff)', icon: 'bi-x-lg', iconColor: 'var(--pe-status-danger, #dc2626)' },
        info: { border: 'var(--pe-color-accent, #0ea5e9)', bg: 'var(--pe-color-surface, #ffffff)', icon: 'bi-info-lg', iconColor: 'var(--pe-color-accent, #0ea5e9)' },
      };
      const t = typeMap[type] || typeMap.info;
      const el = document.createElement('div');
      el.className = 'pointer-events-auto flex items-center p-4 rounded-lg shadow-lg border card animate-fade-in';
      el.style.cssText = `border-color: ${t.border}; background: ${t.bg};`;
      el.innerHTML = `
        <i class="bi ${t.icon} text-xl mr-3" style="color: ${t.iconColor}"></i>
        <p class="text-sm font-semibold flex-1" style="color: var(--pe-color-text, #1e293b)">${message}</p>
        <button type="button" class="ml-3 min-h-[44px] min-w-[44px] flex items-center justify-center" aria-label="Dismiss" style="color: var(--pe-color-text-muted, #64748b)">&times;</button>
      `;
      el.querySelector('button').addEventListener('click', () => el.remove());
      container.appendChild(el);
      setTimeout(() => {
        el.style.opacity = '0';
        el.style.transition = 'opacity 0.2s';
        setTimeout(() => el.remove(), 200);
      }, duration);
    },
  };

  function confirmAction(message, onConfirm) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal-panel modal-fullscreen-mobile" role="dialog" aria-modal="true">
        <h3 class="text-lg font-semibold mb-2">Confirm</h3>
        <p class="text-text-muted mb-6">${message}</p>
        <div class="flex gap-3 justify-end">
          <button type="button" class="btn-secondary" data-cancel>Cancel</button>
          <button type="button" class="btn-danger" data-confirm>Confirm</button>
        </div>
      </div>
    `;
    backdrop.querySelector('[data-cancel]').addEventListener('click', () => backdrop.remove());
    backdrop.querySelector('[data-confirm]').addEventListener('click', () => {
      backdrop.remove();
      if (onConfirm) onConfirm();
    });
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) backdrop.remove();
    });
    document.body.appendChild(backdrop);
  }

  function observeFadeIn() {
    const els = document.querySelectorAll('.fade-in-scroll');
    if (!els.length) return;
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('is-visible');
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
    );
    els.forEach((el) => io.observe(el));
  }

  function initTooltips() {
    document.querySelectorAll('[data-tooltip]').forEach((el) => {
      if (el.closest('.tooltip-wrap')) return;
      const text = el.getAttribute('data-tooltip');
      if (!text) return;
      const wrap = document.createElement('span');
      wrap.className = 'tooltip-wrap';
      el.parentNode.insertBefore(wrap, el);
      wrap.appendChild(el);
      const tip = document.createElement('span');
      tip.className = 'tooltip-text';
      tip.textContent = text;
      wrap.appendChild(tip);
    });
  }

  function animateCounters() {
    document.querySelectorAll('[data-counter]').forEach((el) => {
      const target = parseFloat(el.getAttribute('data-counter')) || 0;
      const prefix = el.getAttribute('data-counter-prefix') || '';
      const suffix = el.getAttribute('data-counter-suffix') || '';
      const duration = 800;
      const start = performance.now();
      function tick(now) {
        const p = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - p, 3);
        const val = Math.round(target * eased);
        el.textContent = prefix + val.toLocaleString() + suffix;
        if (p < 1) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
    });
  }

  function showSkeletons(container) {
    if (!container) return;
    container.innerHTML = '';
    for (let i = 0; i < 4; i++) {
      const row = document.createElement('div');
      row.className = 'skeleton h-12 mb-3 w-full';
      container.appendChild(row);
    }
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }

  function initDomNotificationBells() {
    if (window.__printedgeDomNotifInit) return;
    window.__printedgeDomNotifInit = true;

    function timeAgo(iso) {
      const d = new Date(iso);
      const now = new Date();
      const diff = Math.floor((now - d) / 1000);
      if (diff < 60) return diff + 's ago';
      if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
      if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
      return Math.floor(diff / 86400) + 'd ago';
    }

    function renderForRoot(root, data) {
      const uid = root.getAttribute('data-notification-root');
      const badge = root.querySelector('[data-notification-badge="' + uid + '"]');
      const list = root.querySelector('[data-notification-list="' + uid + '"]');
      const count = data.unread_count || 0;
      if (badge) {
        if (count > 0) {
          badge.textContent = count > 99 ? '99+' : String(count);
          badge.classList.remove('hidden');
        } else {
          badge.classList.add('hidden');
        }
      }
      if (!list) return;
      const items = data.notifications || [];
      if (!items.length) {
        list.innerHTML = '<li class="px-4 py-6 text-text-muted text-center">No notifications</li>';
        return;
      }
      list.innerHTML = items.map((n) => {
        const unreadClass = n.is_read ? '' : ' bg-primary/5';
        const unreadDot = n.is_read ? '' : '<span class="w-2 h-2 rounded-full bg-primary mt-1.5 flex-shrink-0"></span>';
        return '<li class="px-4 py-3 hover:bg-surface transition-colors' + unreadClass + '">' +
          '<a href="' + (n.target_url || '#') + '" class="block notif-link" data-id="' + n.id + '">' +
          '<div class="flex items-start gap-2">' + unreadDot +
          '<div class="flex-1 min-w-0">' +
          '<p class="font-semibold text-text-strong text-sm break-words">' + n.verb + '</p>' +
          '<p class="text-xs text-text-muted mt-0.5 line-clamp-2">' + (n.description || '') + '</p>' +
          '<p class="text-[10px] text-text-muted mt-1">' + (n.actor_name || '') + ' ' + timeAgo(n.created_at) + '</p>' +
          '</div></div></a></li>';
      }).join('');
    }

    function renderAll(data) {
      document.querySelectorAll('[data-notification-root]').forEach((root) => renderForRoot(root, data));
    }

    async function fetchNotifications() {
      try {
        const token = getCsrfToken();
        const headers = { 'X-Requested-With': 'XMLHttpRequest' };
        if (token) headers['X-CSRFToken'] = token;
        const res = await fetch('/api/notifications/', { headers, credentials: 'same-origin' });
        if (res.ok) renderAll(await res.json());
      } catch (_) { /* ignore */ }
    }

    document.querySelectorAll('[data-notification-root]').forEach((root) => {
      const uid = root.getAttribute('data-notification-root');
      const bell = root.querySelector('[data-notification-bell="' + uid + '"]');
      const dropdown = root.querySelector('[data-notification-dropdown="' + uid + '"]');
      const list = root.querySelector('[data-notification-list="' + uid + '"]');
      const markAllBtn = root.querySelector('[data-mark-all-read="' + uid + '"]');
      if (!bell || !dropdown) return;

      bell.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const isHidden = dropdown.classList.contains('hidden');
        dropdown.classList.toggle('hidden');
        bell.setAttribute('aria-expanded', String(!isHidden));
        if (isHidden) fetchNotifications();
        setTimeout(() => { if (document.activeElement === bell) bell.blur(); }, 100);
      });

      if (list) {
        list.addEventListener('click', (e) => {
          const link = e.target.closest('.notif-link');
          if (!link || !link.dataset.id) return;
          fetch('/api/notifications/' + link.dataset.id + '/read/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() || '', 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
          });
        });
      }

      if (markAllBtn) {
        markAllBtn.addEventListener('click', () => {
          fetch('/api/notifications/read-all/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() || '', 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
          }).then(() => fetchNotifications());
        });
      }
    });

    document.addEventListener('click', (e) => {
      document.querySelectorAll('[data-notification-root]').forEach((root) => {
        const uid = root.getAttribute('data-notification-root');
        const bell = root.querySelector('[data-notification-bell="' + uid + '"]');
        const dropdown = root.querySelector('[data-notification-dropdown="' + uid + '"]');
        if (dropdown && bell && !dropdown.contains(e.target) && !bell.contains(e.target)) {
          dropdown.classList.add('hidden');
          bell.setAttribute('aria-expanded', 'false');
        }
      });
    });

    document.addEventListener('printedge:notifications-sync', (e) => {
      if (e.detail) renderAll(e.detail);
    });

    fetchNotifications();
  }

  // Wait for Alpine to be ready before defining components
  function initNotificationBell() {
    if (typeof Alpine === 'undefined') return;
    Alpine.data('notifBell', () => ({
      open: false,
      unreadCount: 0,
      notifications: [],
      load() {
        fetch('/api/notifications/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
          .then(r => r.json())
          .then(data => {
            this.notifications = data.notifications || [];
            this.unreadCount = data.unread_count || 0;
            if (this.unreadCount > 0 && !localStorage.getItem('notifSoundDisabled')) {
              try {
                const audio = new Audio('data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YU9vT18=');
                audio.play().catch(() => {});
              } catch (e) {}
            }
          })
          .catch(() => {});
      },
      toggle() {
        this.open = !this.open;
        if (this.open) this.load();
      },
      markRead(id) {
        fetch(`/api/notifications/${id}/read/`, {
          method: 'POST',
          headers: { 'X-CSRFToken': this.getCsrf() || '', 'X-Requested-With': 'XMLHttpRequest' },
        });
      },
      markAllRead() {
        fetch('/api/notifications/read-all/', {
          method: 'POST',
          headers: { 'X-CSRFToken': this.getCsrf() || '', 'X-Requested-With': 'XMLHttpRequest' },
        }).then(() => this.load());
      },
      formatTime(iso) {
        const d = new Date(iso);
        const now = new Date();
        const diff = Math.floor((now - d) / 1000);
        if (diff < 60) return diff + 's ago';
        if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
        if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
        return Math.floor(diff / 86400) + 'd ago';
      },
      getCsrf() { return getCsrfToken(); },
      init() {
        this.load();
        setInterval(() => this.load(), 30000);
      }
    }));
  }

  // Initialize when DOM is ready
  function init() {
    observeFadeIn();
    initTooltips();
    animateCounters();
    initDomNotificationBells();
    initNotificationBell();
  }

  // Try multiple times for Alpine
  let alpineTries = 0;
  function waitForAlpine() {
    if (typeof Alpine !== 'undefined') {
      initNotificationBell();
      document.querySelectorAll('[x-data]').forEach(el => {
        try { Alpine.initTree(el); } catch (e) {}
      });
    } else if (alpineTries < 20) {
      alpineTries++;
      setTimeout(waitForAlpine, 100);
    }
  }

  document.addEventListener('DOMContentLoaded', init);
  document.addEventListener('alpine:init', () => {
    initNotificationBell();
  });

  // Fallback for Alpine init
  setTimeout(waitForAlpine, 500);

  const pdfUtils = {
    async getPdfPageCount(file) {
      if (typeof pdfjsLib === 'undefined') {
        console.warn('pdfjsLib is not loaded');
        return 1;
      }
      try {
        const arrayBuffer = await file.arrayBuffer();
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        return pdf.numPages || 1;
      } catch (e) {
        console.error('Error reading PDF pages:', e);
        return 1;
      }
    }
  };

  /**
   * Returns Chart.js color palette that respects the current theme.
   * Reads CSS custom properties so it works with theme switching.
   */
  function chartColors() {
    const style = getComputedStyle(document.documentElement);
    const primary = style.getPropertyValue('--pe-color-primary').trim() || '#4f46e5';
    const accent = style.getPropertyValue('--pe-color-accent').trim() || '#0ea5e9';
    const success = style.getPropertyValue('--pe-status-success').trim() || '#059669';
    const warning = style.getPropertyValue('--pe-status-warning').trim() || '#d97706';
    const danger = style.getPropertyValue('--pe-status-danger').trim() || '#dc2626';
    const info = style.getPropertyValue('--pe-status-info').trim() || '#0ea5e9';
    const text = style.getPropertyValue('--pe-color-text').trim() || '#1e293b';
    const muted = style.getPropertyValue('--pe-color-text-muted').trim() || '#64748b';
    const border = style.getPropertyValue('--pe-color-border').trim() || '#e2e8f0';
    const surface = style.getPropertyValue('--pe-color-surface').trim() || '#ffffff';
    return {
      primary,
      accent,
      success,
      warning,
      danger,
      info,
      text,
      muted,
      border,
      surface,
      gridColor: border + '99',
      makeGrid() {
        return { color: this.gridColor, drawBorder: false };
      },
      defaults(chartDefaults) {
        chartDefaults.color = muted;
        chartDefaults.font = { family: 'Inter, ui-sans-serif, system-ui, sans-serif', size: 12 };
        const tb = chartDefaults.plugins.tooltip;
        tb.backgroundColor = surface;
        tb.borderColor = border;
        tb.borderWidth = 1;
        tb.padding = 10;
        tb.cornerRadius = 8;
        tb.titleColor = text;
        tb.bodyColor = muted;
        tb.titleFont = { weight: 'bold' };
      },
      line(data, fillColor) {
        return { borderColor: primary, backgroundColor: fillColor || primary + '1a', fill: true, tension: 0.35, pointRadius: 3, pointHoverRadius: 6, borderWidth: 2 };
      },
      bar(color) {
        return { backgroundColor: color || primary, borderRadius: 4 };
      },
      doughnut(colors) {
        return { backgroundColor: colors || [warning, info, success, muted, danger], borderWidth: 0, hoverOffset: 6 };
      },
      pie(colors) {
        return { backgroundColor: colors || [primary, accent, warning, danger], borderWidth: 0, hoverOffset: 8 };
      },
      barH(color) {
        return { backgroundColor: color || primary, borderRadius: 6 };
      },
    };
  }

  function sparkline(canvas, data, color, height) {
    if (!canvas || !data || data.length < 2) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement.getBoundingClientRect();
    const w = rect.width || 80;
    const h = height || 24;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    const max = Math.max(...data, 1);
    const min = Math.min(...data, 0);
    const range = max - min || 1;
    const pad = 1;
    const xs = data.map((_, i) => pad + (i / (data.length - 1)) * (w - pad * 2));
    const ys = data.map(v => h - pad - ((v - min) / range) * (h - pad * 2));
    ctx.beginPath();
    ctx.moveTo(xs[0], ys[0]);
    for (let i = 1; i < data.length; i++) {
      const cpx = (xs[i - 1] + xs[i]) / 2;
      ctx.bezierCurveTo(cpx, ys[i - 1], cpx, ys[i], xs[i], ys[i]);
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(xs[xs.length - 1], ys[ys.length - 1], 2, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  }

  function heatmap(canvas, data) {
    if (!canvas || !data || data.length !== 7) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement.getBoundingClientRect();
    const w = rect.width || 300;
    const h = rect.height || 120;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    const rows = 7, cols = 24;
    const cw = w / cols, ch = h / rows;
    const max = Math.max(...data.flat(), 1);
    const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
    const style = getComputedStyle(document.documentElement);
    const primary = style.getPropertyValue('--pe-color-primary').trim() || '#4f46e5';
    const muted = style.getPropertyValue('--pe-color-text-muted').trim() || '#64748b';
    ctx.textBaseline = 'middle';
    ctx.font = '8px Inter, ui-sans-serif';
    for (let r = 0; r < rows; r++) {
      ctx.fillStyle = muted;
      ctx.textAlign = 'right';
      ctx.fillText(days[r], -2, r * ch + ch / 2);
      for (let c = 0; c < cols; c++) {
        const val = data[r][c];
        const alpha = val / max;
        ctx.fillStyle = alpha > 0 ? primary.replace(')', `, ${0.08 + alpha * 0.6})`) : 'transparent';
        const x = c * cw, y = r * ch;
        ctx.beginPath();
        ctx.roundRect(x + 1, y + 1, cw - 2, ch - 2, 2);
        ctx.fill();
        if (val > 0) {
          ctx.fillStyle = alpha > 0.5 ? '#fff' : muted;
          ctx.textAlign = 'center';
          ctx.font = '7px Inter, ui-sans-serif';
          if (cw > 16) ctx.fillText(val > 99 ? '99+' : val, x + cw / 2, y + ch / 2);
        }
      }
    }
  }

  global.PrintEdge = {
    Toast,
    confirmAction,
    observeFadeIn,
    initTooltips,
    animateCounters,
    showSkeletons,
    getCsrfToken,
    pdfUtils,
    chartColors,
    sparkline,
    heatmap,
  };
})(window);
