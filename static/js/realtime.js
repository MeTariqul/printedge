/**
 * Supabase Realtime notifications (falls back to polling)
 */
(function (global) {
  'use strict';

  const POLL_MS = 30000;
  let pollTimer = null;
  let sharedAudioCtx = null;
  
  function getOrCreateAudioCtx() {
    if (!sharedAudioCtx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      sharedAudioCtx = new Ctx();
    }
    return sharedAudioCtx;
  }

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

  function playDing() {
    try {
      const ctx = getOrCreateAudioCtx();
      if (ctx.state === 'suspended') {
        ctx.resume();
      }
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      
      osc.connect(gain);
      gain.connect(ctx.destination);
      
      osc.type = 'sine';
      osc.frequency.setValueAtTime(800, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(1200, ctx.currentTime + 0.1);
      
      gain.gain.setValueAtTime(0, ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0.5, ctx.currentTime + 0.05);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
      
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.5);
    } catch (e) {
      /* audio play failed */
    }
  }

  function onNewNotification(payload) {
    const title = payload.new?.title || payload.title || payload.new?.verb || 'New notification';
    if (global.PrintEdge && global.PrintEdge.Toast) {
      global.PrintEdge.Toast.show(title, 'info');
    }
    
    // Play sound if enabled
    const soundEnabled = localStorage.getItem('printedge_sound_enabled') !== 'false';
    if (soundEnabled) {
       playDing();
    }
    
    // Desktop Notification
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification("Print-Edge", {
        body: title,
        icon: '/static/icons/icon-192.png'
      });
    }
    document.dispatchEvent(new CustomEvent('printedge:notification', { detail: payload }));
    const badge = document.querySelector('[data-notification-badge]');
    if (badge) {
      const n = parseInt(badge.textContent, 10) || 0;
      badge.textContent = String(n + 1);
      badge.classList.remove('hidden');
    }
    fetchNotifications();
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
        const channel = client
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

    // Sound toggle logic
    const soundEnabled = localStorage.getItem('printedge_sound_enabled') !== 'false';
    const soundBtns = document.querySelectorAll('[data-notification-sound]');
    const soundIcons = document.querySelectorAll('[data-sound-icon]');
    
    function updateSoundIcons(enabled) {
      soundIcons.forEach(icon => {
        if (enabled) {
          icon.classList.remove('bi-volume-mute-fill');
          icon.classList.add('bi-volume-up-fill');
        } else {
          icon.classList.remove('bi-volume-up-fill');
          icon.classList.add('bi-volume-mute-fill');
        }
      });
    }
    
    updateSoundIcons(soundEnabled);
    
    soundBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const current = localStorage.getItem('printedge_sound_enabled') !== 'false';
        const next = !current;
        localStorage.setItem('printedge_sound_enabled', String(next));
        updateSoundIcons(next);
        
        // Also request notification permission on first interaction
        if (next && "Notification" in window && Notification.permission !== "granted" && Notification.permission !== "denied") {
          Notification.requestPermission();
        }
      });
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})(window);
