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
      const colors = {
        success: 'border-emerald-500/40 bg-emerald-50',
        error: 'border-red-500/40 bg-red-50',
        info: 'border-primary/40 bg-white',
      };
      const icons = {
        success: 'bi-check-lg text-emerald-600',
        error: 'bi-x-lg text-red-600',
        info: 'bi-info-lg text-primary',
      };
      const el = document.createElement('div');
      el.className = `pointer-events-auto flex items-center p-4 rounded-lg shadow-lg border card animate-fade-in ${colors[type] || colors.info}`;
      el.innerHTML = `
        <i class="bi ${icons[type] || icons.info} text-xl mr-3"></i>
        <p class="text-sm font-semibold text-text flex-1">${message}</p>
        <button type="button" class="ml-3 text-gray-400 hover:text-gray-600" aria-label="Dismiss">&times;</button>
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
        list.innerHTML = '<li class="px-4 py-6 text-slate-500 text-center">No notifications</li>';
        return;
      }
      list.innerHTML = items.map((n) => {
        const unreadClass = n.is_read ? '' : ' bg-brand-500/5';
        const unreadDot = n.is_read ? '' : '<span class="w-2 h-2 rounded-full bg-brand-400 mt-1.5 flex-shrink-0"></span>';
        return '<li class="px-4 py-3 hover:bg-white/5 transition-colors' + unreadClass + '">' +
          '<a href="' + (n.target_url || '#') + '" class="block notif-link" data-id="' + n.id + '">' +
          '<div class="flex items-start gap-2">' + unreadDot +
          '<div class="flex-1 min-w-0">' +
          '<p class="font-semibold text-white text-sm break-words">' + n.verb + '</p>' +
          '<p class="text-xs text-slate-400 mt-0.5 line-clamp-2">' + (n.description || '') + '</p>' +
          '<p class="text-[10px] text-slate-500 mt-1">' + (n.actor_name || '') + ' ' + timeAgo(n.created_at) + '</p>' +
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

  global.PrintEdge = {
    Toast,
    confirmAction,
    observeFadeIn,
    initTooltips,
    animateCounters,
    showSkeletons,
    getCsrfToken,
    pdfUtils,
  };
})(window);
