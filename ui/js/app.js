/**
 * Liquid Glass Clipboard Manager — Core Application Logic
 * Handles clip list rendering, search, keyboard navigation, and API calls.
 *
 * Security: All user data is rendered via DOM text APIs (textContent)
 * or escaped before insertion into innerHTML to prevent XSS.
 */

const App = (() => {
  let clips = [];
  let selectedIndex = -1;
  let currentTab = 'history';
  let searchQuery = '';

  // ── DOM Refs ─────────────────────────────────────────────
  const clipList = () => document.getElementById('clip-list');
  const searchInput = () => document.getElementById('search-input');
  const toastEl = () => document.getElementById('toast');

  // ── Initialization ───────────────────────────────────────
  async function init() {
    detectTheme();
    await loadHistory();
    bindGlobalKeys();
    bindSearch();
    bindTabs();

    // Auto-focus search input
    setTimeout(() => {
      const input = searchInput();
      if (input) input.focus();
    }, 100);

    // Hide window when it loses focus (stealth spotlight behavior)
    window.addEventListener('blur', async () => {
      if (Editor && Editor.isOpen()) return;
      try {
        await pywebview.api.hide_window();
      } catch (e) { }
    });

    // Listen for new clips pushed from Python
    window.addEventListener('pywebviewready', () => {
      console.log('pywebview bridge ready');
    });
  }

  // ── Theme Detection ──────────────────────────────────────
  function detectTheme() {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = (dark) => {
      document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    };
    apply(mq.matches);
    mq.addEventListener('change', (e) => apply(e.matches));
  }

  // ── Data Loading ─────────────────────────────────────────
  async function loadHistory() {
    try {
      clips = await pywebview.api.get_history();
    } catch (e) {
      clips = [];
      console.error('Failed to load history:', e);
    }
    renderClips();
  }

  // ── Filtered Clips (single source of truth) ─────────────
  function getFilteredClips() {
    return clips.filter(clip => {
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (clip.text || '').toLowerCase().includes(q) ||
        (clip.language || '').toLowerCase().includes(q);
    });
  }

  // ── Rendering (XSS-safe) ────────────────────────────────
  function renderClips() {
    const container = clipList();
    if (!container) return;

    const filtered = getFilteredClips();

    if (filtered.length === 0) {
      container.innerHTML = '';
      const emptyState = document.createElement('div');
      emptyState.className = 'empty-state';
      emptyState.innerHTML = `
        <div class="icon">📋</div>
        <p>${searchQuery ? 'No matching clips found' : 'Clipboard history is empty'}<br>
        <span style="font-size:11px; color: var(--text-tertiary)">
          Copy something to get started
        </span></p>`;
      container.appendChild(emptyState);
      return;
    }

    // Clear and rebuild using DOM APIs to prevent XSS
    container.innerHTML = '';
    const fragment = document.createDocumentFragment();

    filtered.forEach((clip, i) => {
      const el = _createClipElement(clip, i);
      fragment.appendChild(el);
    });

    container.appendChild(fragment);
  }

  /**
   * Create a clip item DOM element safely using DOM APIs.
   * No user data is ever inserted via innerHTML.
   */
  function _createClipElement(clip, index) {
    const item = document.createElement('div');
    item.className = `clip-item ${index === selectedIndex ? 'selected' : ''} ${clip.pinned ? 'pinned' : ''}`.trim();
    item.dataset.id = clip.id;
    item.dataset.index = index;

    // Double-click to paste
    item.addEventListener('dblclick', () => pasteItem(clip.id));
    // Single click to select
    item.addEventListener('click', () => {
      selectedIndex = index;
      renderClips();
    });

    // ── Header row ──
    const header = document.createElement('div');
    header.className = 'clip-header';

    const meta = document.createElement('div');
    meta.className = 'clip-meta';

    const langBadge = document.createElement('span');
    langBadge.className = 'clip-lang';
    langBadge.textContent = clip.language || 'plaintext';
    meta.appendChild(langBadge);

    const timeEl = document.createElement('span');
    timeEl.className = 'clip-time';
    timeEl.textContent = formatTime(clip.timestamp);
    meta.appendChild(timeEl);

    if (clip.pinned) {
      const pinIcon = document.createElement('span');
      pinIcon.style.cssText = 'color: var(--pin-color); font-size: 12px;';
      pinIcon.textContent = '📌';
      meta.appendChild(pinIcon);
    }

    header.appendChild(meta);

    // ── Action buttons ──
    const actions = document.createElement('div');
    actions.className = 'clip-actions';

    actions.appendChild(_createActionBtn('✏️', 'Edit', () => editItem(clip.id)));
    actions.appendChild(_createActionBtn('📌', 'Pin', () => togglePin(clip.id)));
    actions.appendChild(_createActionBtn('📋', 'Copy', () => copyItem(clip.id)));
    actions.appendChild(_createActionBtn('✕', 'Delete', () => deleteItem(clip.id), true));

    header.appendChild(actions);
    item.appendChild(header);

    // ── Preview ──
    const preview = document.createElement('div');
    preview.className = 'clip-preview';
    preview.textContent = clip.preview || clip.text || '';
    item.appendChild(preview);

    return item;
  }

  function _createActionBtn(emoji, title, handler, isDanger = false) {
    const btn = document.createElement('button');
    btn.className = `btn btn-icon${isDanger ? ' btn-danger' : ''}`;
    btn.title = title;
    btn.textContent = emoji;
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      handler();
    });
    return btn;
  }

  // ── Search ───────────────────────────────────────────────
  function bindSearch() {
    const input = searchInput();
    if (!input) return;
    input.addEventListener('input', (e) => {
      searchQuery = e.target.value;
      selectedIndex = -1;
      renderClips();
    });
  }

  // ── Tabs ─────────────────────────────────────────────────
  function bindTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        switchTab(tab);
      });
    });
  }

  function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === `panel-${tab}`));

    if (tab === 'settings') {
      Settings.load();
    }
  }

  // ── Keyboard Navigation ──────────────────────────────────
  function bindGlobalKeys() {
    document.addEventListener('keydown', async (e) => {
      // Escape → hide window
      if (e.key === 'Escape') {
        if (Editor.isOpen()) {
          Editor.close();
        } else {
          try { await pywebview.api.hide_window(); } catch (_) { }
        }
        return;
      }

      // Only navigate when on history tab and not in editor
      if (currentTab !== 'history' || Editor.isOpen()) return;

      const filtered = getFilteredClips();

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIndex = Math.min(selectedIndex + 1, filtered.length - 1);
        renderClips();
        scrollToSelected();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = Math.max(selectedIndex - 1, 0);
        renderClips();
        scrollToSelected();
      } else if (e.key === 'Enter' && selectedIndex >= 0) {
        e.preventDefault();
        const clip = filtered[selectedIndex];
        if (clip) pasteItem(clip.id);
      }
    });
  }

  function scrollToSelected() {
    const el = document.querySelector('.clip-item.selected');
    if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  // ── Actions ──────────────────────────────────────────────
  async function pasteItem(id) {
    try {
      await pywebview.api.paste_item(id);
      toast('Copied to clipboard');
    } catch (e) {
      console.error('Paste failed:', e);
    }
  }

  async function copyItem(id) {
    try {
      await pywebview.api.copy_item(id);
      toast('Copied to clipboard');
    } catch (e) {
      console.error('Copy failed:', e);
    }
  }

  async function deleteItem(id) {
    try {
      const success = await pywebview.api.delete_item(id);
      if (success) {
        clips = clips.filter(c => c.id !== id);
        if (selectedIndex >= clips.length) selectedIndex = clips.length - 1;
        renderClips();
        toast('Item deleted');
      }
    } catch (e) {
      console.error('Delete failed:', e);
    }
  }

  async function togglePin(id) {
    try {
      const updated = await pywebview.api.toggle_pin(id);
      if (updated) {
        const idx = clips.findIndex(c => c.id === id);
        if (idx !== -1) clips[idx] = { ...clips[idx], ...updated };
        renderClips();
        toast(updated.pinned ? 'Pinned' : 'Unpinned');
      }
    } catch (e) {
      console.error('Pin toggle failed:', e);
    }
  }

  function editItem(id) {
    const clip = clips.find(c => c.id === id);
    if (clip) Editor.open(clip);
  }

  async function clearHistory() {
    // Confirmation dialog for destructive action
    if (!confirm('Are you sure you want to clear all clipboard history? This cannot be undone.')) {
      return;
    }
    try {
      await pywebview.api.clear_history();
      clips = [];
      selectedIndex = -1;
      renderClips();
      toast('History cleared');
    } catch (e) {
      console.error('Clear failed:', e);
    }
  }

  // ── Notifications ────────────────────────────────────────
  let _toastTimeout = null;
  function toast(msg) {
    const el = toastEl();
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    if (_toastTimeout) clearTimeout(_toastTimeout);
    _toastTimeout = setTimeout(() => el.classList.remove('show'), 2000);
  }

  // ── Utilities ────────────────────────────────────────────
  function formatTime(ts) {
    const now = Date.now() / 1000;
    const diff = now - ts;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return new Date(ts * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  // ── Public callback for Python to push new clips ─────────
  function onNewClip(clip) {
    // Remove dupe if exists
    clips = clips.filter(c => c.id !== clip.id);
    clips.unshift(clip);
    if (currentTab === 'history') renderClips();
  }

  // ── Public API ───────────────────────────────────────────
  return {
    init,
    loadHistory,
    renderClips,
    pasteItem,
    copyItem,
    deleteItem,
    togglePin,
    editItem,
    clearHistory,
    toast,
    onNewClip,
    switchTab,
  };
})();

// Boot
document.addEventListener('DOMContentLoaded', App.init);