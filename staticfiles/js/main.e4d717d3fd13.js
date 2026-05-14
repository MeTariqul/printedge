// ── PrintEase Core JS ──

// ── Theme ──
const ThemeManager = {
  init() {
    document.documentElement.setAttribute('data-theme', 'light');
    localStorage.setItem('pe-theme', 'light');
  },
  apply(theme) {},
  toggle() {}
};

// ── Toast ──
const Toast = {
  container: null,
  init() {
    this.container = document.getElementById('toast-container');
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.id = 'toast-container';
      this.container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
      document.body.appendChild(this.container);
    }
  },
  show(message, type = 'info', duration = 4000) {
    const icons = { success: 'bi-check-circle-fill', danger: 'bi-x-circle-fill', warning: 'bi-exclamation-triangle-fill', info: 'bi-info-circle-fill' };
    const colors = { success: '#10b981', danger: '#ef4444', warning: '#f59e0b', info: '#6366f1' };
    const t = document.createElement('div');
    t.className = 'pe-toast';
    t.innerHTML = `
      <i class="bi ${icons[type] || icons.info}" style="color:${colors[type]};font-size:1.1rem;flex-shrink:0;margin-top:2px"></i>
      <div class="flex-grow-1"><span style="color:var(--text);font-size:0.875rem">${message}</span></div>
      <button onclick="this.closest('.pe-toast').remove()" style="background:none;border:none;color:var(--text-muted);cursor:pointer;padding:0;line-height:1"><i class="bi bi-x"></i></button>
    `;
    this.container.appendChild(t);
    if (duration > 0) setTimeout(() => { t.classList.add('hide'); setTimeout(() => t.remove(), 300); }, duration);
    return t;
  }
};

// ── Sidebar ──
const Sidebar = {
  sidebar: null,
  overlay: null,
  content: null,
  navbar: null,
  collapsed: false,
  init() {
    this.sidebar = document.getElementById('adminSidebar');
    this.overlay = document.getElementById('sidebarOverlay');
    this.content = document.getElementById('adminContent');
    this.navbar = document.getElementById('adminNavbar');
    const saved = localStorage.getItem('pe-sidebar');
    if (saved === 'collapsed' && window.innerWidth >= 1200) this.collapse(false);
    if (this.overlay) this.overlay.addEventListener('click', () => this.closeMobile());
  },
  toggle() {
    if (window.innerWidth < 1200) {
      this.toggleMobile();
    } else {
      this.collapsed ? this.expand() : this.collapse();
    }
  },
  collapse(save = true) {
    this.collapsed = true;
    this.sidebar?.classList.add('collapsed');
    this.content?.classList.add('sidebar-collapsed');
    this.navbar?.classList.add('sidebar-collapsed');
    if (save) localStorage.setItem('pe-sidebar', 'collapsed');
  },
  expand(save = true) {
    this.collapsed = false;
    this.sidebar?.classList.remove('collapsed');
    this.content?.classList.remove('sidebar-collapsed');
    this.navbar?.classList.remove('sidebar-collapsed');
    if (save) localStorage.setItem('pe-sidebar', 'expanded');
  },
  toggleMobile() {
    const isOpen = this.sidebar?.classList.contains('mobile-open');
    if (isOpen) this.closeMobile(); else this.openMobile();
  },
  openMobile() {
    this.sidebar?.classList.add('mobile-open');
    this.overlay?.classList.add('show');
    document.body.style.overflow = 'hidden';
  },
  closeMobile() {
    this.sidebar?.classList.remove('mobile-open');
    this.overlay?.classList.remove('show');
    document.body.style.overflow = '';
  }
};

// ── Global Search ──
const GlobalSearch = {
  overlay: null,
  input: null,
  results: null,
  init() {
    this.overlay = document.getElementById('searchOverlay');
    this.input = document.getElementById('searchInput');
    this.results = document.getElementById('searchResults');
    document.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); this.open(); }
      if (e.key === 'Escape') this.close();
    });
    this.input?.addEventListener('input', () => this.search(this.input.value));
    this.overlay?.addEventListener('click', e => { if (e.target === this.overlay) this.close(); });
  },
  open() {
    this.overlay?.classList.add('open');
    setTimeout(() => this.input?.focus(), 50);
  },
  close() {
    this.overlay?.classList.remove('open');
    if (this.input) this.input.value = '';
    if (this.results) this.results.innerHTML = '';
  },
  search(q) {
    if (!q.trim()) { if (this.results) this.results.innerHTML = ''; return; }
    // Placeholder search — replace with real API call
    if (this.results) {
      this.results.innerHTML = `<div class="search-result-item text-muted"><i class="bi bi-search me-2"></i>Searching for "${q}"...</div>`;
    }
    clearTimeout(this._t);
    this._t = setTimeout(() => this.fetchResults(q), 300);
  },
  async fetchResults(q) {
    try {
      const res = await fetch(`/admin/api/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      this.renderResults(data.results || []);
    } catch {
      if (this.results) this.results.innerHTML = '<div class="search-result-item text-muted">No results found</div>';
    }
  },
  renderResults(items) {
    if (!this.results) return;
    if (!items.length) { this.results.innerHTML = '<div class="search-result-item text-muted">No results found</div>'; return; }
    this.results.innerHTML = items.map(item => `
      <a href="${item.url}" class="search-result-item text-decoration-none">
        <div class="activity-icon" style="background:var(--primary-light);color:var(--primary)"><i class="bi ${item.icon || 'bi-file-text'}"></i></div>
        <div><div style="color:var(--text);font-weight:600;font-size:.875rem">${item.title}</div><div style="color:var(--text-muted);font-size:.75rem">${item.subtitle || ''}</div></div>
        <span class="badge badge-${item.type} ms-auto">${item.type}</span>
      </a>`).join('');
  }
};

// ── FAB ──
const FAB = {
  btn: null,
  menu: null,
  open: false,
  init() {
    this.btn = document.getElementById('fabMain');
    this.menu = document.getElementById('fabMenu');
    this.btn?.addEventListener('click', () => this.toggle());
    document.addEventListener('click', e => {
      if (!e.target.closest('#fabContainer')) this.close();
    });
  },
  toggle() { this.open ? this.close() : this.openMenu(); },
  openMenu() {
    this.open = true;
    this.menu?.classList.add('open');
    this.btn?.querySelector('i')?.classList.replace('bi-plus', 'bi-x');
  },
  close() {
    this.open = false;
    this.menu?.classList.remove('open');
    this.btn?.querySelector('i')?.classList.replace('bi-x', 'bi-plus');
  }
};

// ── Kanban ──
const Kanban = {
  dragging: null,
  init() {
    document.querySelectorAll('.kanban-card').forEach(card => {
      card.setAttribute('draggable', 'true');
      card.addEventListener('dragstart', e => { this.dragging = card; card.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; });
      card.addEventListener('dragend', () => { card.classList.remove('dragging'); this.dragging = null; document.querySelectorAll('.kanban-drop-target').forEach(c => c.classList.remove('kanban-drop-target')); });
    });
    document.querySelectorAll('.kanban-col-body').forEach(col => {
      col.addEventListener('dragover', e => { e.preventDefault(); col.classList.add('kanban-drop-target'); });
      col.addEventListener('dragleave', () => col.classList.remove('kanban-drop-target'));
      col.addEventListener('drop', e => {
        e.preventDefault();
        col.classList.remove('kanban-drop-target');
        if (this.dragging) {
          col.appendChild(this.dragging);
          const newStatus = col.closest('.kanban-col')?.dataset.status;
          const orderId = this.dragging.dataset.orderId;
          if (newStatus && orderId) this.updateStatus(orderId, newStatus);
        }
      });
    });
  },
  async updateStatus(orderId, status) {
    try {
      await fetch(`/admin/api/orders/${orderId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
        body: JSON.stringify({ status })
      });
      Toast.show(`Order status updated to ${status}`, 'success');
    } catch { Toast.show('Failed to update status', 'danger'); }
  }
};

// ── Multi-step Wizard ──
const Wizard = {
  current: 1,
  total: 6,
  data: {},
  init(totalSteps) {
    this.total = totalSteps || 6;
    this.current = 1;
    this.render();
  },
  next() {
    if (this.current < this.total) { this.current++; this.render(); }
  },
  prev() {
    if (this.current > 1) { this.current--; this.render(); }
  },
  goTo(step) {
    if (step >= 1 && step <= this.total) { this.current = step; this.render(); }
  },
  render() {
    document.querySelectorAll('.wizard-step').forEach((el, i) => {
      el.classList.toggle('active', i + 1 === this.current);
      el.classList.toggle('done', i + 1 < this.current);
    });
    document.querySelectorAll('.wizard-panel').forEach((el, i) => {
      el.classList.toggle('d-none', i + 1 !== this.current);
    });
    document.getElementById('wizardPrev')?.toggleAttribute('disabled', this.current === 1);
    const nextBtn = document.getElementById('wizardNext');
    if (nextBtn) {
      if (this.current === this.total) {
        nextBtn.textContent = 'Place Order';
        nextBtn.className = nextBtn.className.replace('btn-primary', 'btn-success');
      } else {
        nextBtn.innerHTML = 'Next <i class="bi bi-arrow-right ms-1"></i>';
      }
    }
  }
};

// ── Bulk Select ──
const BulkSelect = {
  init() {
    const selectAll = document.getElementById('selectAll');
    if (!selectAll) return;
    selectAll.addEventListener('change', () => {
      document.querySelectorAll('.row-checkbox').forEach(cb => cb.checked = selectAll.checked);
      this.updateCount();
    });
    document.querySelectorAll('.row-checkbox').forEach(cb => {
      cb.addEventListener('change', () => this.updateCount());
    });
  },
  updateCount() {
    const count = document.querySelectorAll('.row-checkbox:checked').length;
    const el = document.getElementById('selectedCount');
    if (el) el.textContent = `${count} Selected`;
    const bar = document.getElementById('bulkActionBar');
    if (bar) bar.classList.toggle('d-none', count === 0);
  },
  getSelected() {
    return Array.from(document.querySelectorAll('.row-checkbox:checked')).map(cb => cb.value);
  }
};

// ── Price Calculator ──
const PriceCalc = {
  rates: { bw_single: 2, bw_double: 3, color_single: 5, color_double: 8 },
  addons: { spiral_bind: 20, comb_bind: 15, stapled: 5, lamination: 15, color_cover: 10 },
  calculate(pages, copies, printType, sides, addons = [], discount = 0, urgent = false) {
    const key = `${printType}_${sides}`;
    const perPage = this.rates[key] || 2;
    let base = pages * copies * perPage;
    let addonCost = addons.reduce((sum, a) => sum + (this.addons[a] || 0), 0);
    if (urgent) base *= 1.5;
    const bulkDiscount = pages >= 200 ? 0.15 : pages >= 100 ? 0.10 : pages >= 50 ? 0.05 : 0;
    const discountAmt = base * (Math.max(bulkDiscount, discount / 100));
    return { base, addons: addonCost, discount: discountAmt, total: Math.max(0, base - discountAmt + addonCost) };
  }
};

// ── Utility ──
function getCSRF() {
  return document.querySelector('meta[name=csrf-token]')?.content || '';
}

function formatCurrency(n) {
  return '৳ ' + Number(n).toLocaleString('en-IN', { minimumFractionDigits: 0 });
}

function timeAgo(dateStr) {
  const diff = (Date.now() - new Date(dateStr)) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

async function apiCall(url, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
  ThemeManager.init();
  Toast.init();
  Sidebar.init();
  GlobalSearch.init();
  FAB.init();
  Kanban.init();
  BulkSelect.init();

  // Theme toggle buttons
  document.querySelectorAll('[data-theme-toggle]').forEach(el => {
    el.addEventListener('change', e => ThemeManager.apply(e.target.value));
    el.addEventListener('click', e => {
      if (el.tagName === 'BUTTON') ThemeManager.toggle();
    });
  });

  // Confirm dialogs
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', e => {
      if (!confirm(el.dataset.confirm)) e.preventDefault();
    });
  });

  // Make all unlinked buttons and anchors respond
  document.addEventListener('click', e => {
    const link = e.target.closest('a[href="#"]');
    if (link && !link.hasAttribute('data-bs-toggle')) {
      e.preventDefault();
      Toast.show('Feature coming soon', 'info');
    }
  });
});