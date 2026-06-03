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

  global.PrintEdge = {
    Toast,
    confirmAction,
    observeFadeIn,
    initTooltips,
    animateCounters,
    showSkeletons,
    getCsrfToken,
  };
})(window);
