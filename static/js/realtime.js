/**
 * Supabase Realtime notifications (falls back to polling)
 */
(function (global) {
  'use strict';

  const POLL_MS = 30000;
  let pollTimer = null;
  
  function getCookie(name) {
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.startsWith(name + '=')) {
          return decodeURIComponent(cookie.substring(name.length + 1));
        }
      }
    }
    return '';
  }

  function onNewNotification(payload) {
    if (global.PrintEdge && global.PrintEdge.Toast) {
      const title = payload.new?.title || payload.title || 'New notification';
      global.PrintEdge.Toast.show(title, 'info');
    }
    document.dispatchEvent(new CustomEvent('printedge:notification', { detail: payload }));
    const badge = document.querySelector('[data-notification-count]');
    if (badge) {
      const n = parseInt(badge.textContent, 10) || 0;
      badge.textContent = String(n + 1);
      badge.classList.remove('hidden');
    }
  }

  async function fetchNotifications() {
    const headers = { 'X-Requested-With': 'XMLHttpRequest' };
    const csrf = getCookie('csrftoken');
    if (csrf) headers['X-CSRFToken'] = csrf;
    try {
      const res = await fetch('/api/notifications/', { headers, credentials: 'same-origin' });
      if (!res.ok) return;
      const data = await res.json();
      document.dispatchEvent(new CustomEvent('printedge:notifications-sync', { detail: data }));
    } catch (_) {
      /* ignore */
    }
  }

  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(fetchNotifications, POLL_MS);
  }

  function initSupabase(config) {
    if (!config.url || !config.anonKey || !config.userId) {
      startPolling();
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js';
    script.onload = () => {
      try {
        const client = global.supabase.createClient(config.url, config.anonKey);
        channel = client
          .channel('notifications-' + config.userId)
          .on(
            'postgres_changes',
            {
              event: 'INSERT',
              schema: 'public',
              table: 'core_notification',
              filter: 'recipient_id=eq.' + config.userId,
            },
            (payload) => onNewNotification(payload)
          )
          .subscribe((status) => {
            if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT') {
              startPolling();
            }
          });
      } catch (_) {
        startPolling();
      }
    };
    script.onerror = () => startPolling();
    document.head.appendChild(script);
  }

  function init() {
    const el = document.getElementById('supabase-realtime-config');
    if (!el) {
      startPolling();
      return;
    }
    let config = {};
    try {
      config = JSON.parse(el.textContent);
    } catch (_) {
      startPolling();
      return;
    }
    initSupabase(config);
    fetchNotifications();
  }

  document.addEventListener('DOMContentLoaded', init);
})(window);
