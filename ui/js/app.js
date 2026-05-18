/**
 * Liquid Glass Clipboard Manager — Core Application Logic
 * Handles clip list rendering, search, keyboard navigation, and API calls.
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

  // ── Rendering ────────────────────────────────────────────
  function renderClips() {
    const container = clipList();
    if (!container) return;

    const filtered = clips.filter(clip => {
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return clip.text.toLowerCase().includes(q) ||
        clip.language.toLowerCase().includes(q);
    });

    if (filtered.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="icon">📋</div>
          <p>${searchQuery ? 'No matching clips found' : 'Clipboard history is empty'}<br>
          <span style="font-size:11px; color: var(--text-tertiary)">
            Copy something to get started
          </span></p>
        </div>`;
      return;
    }

    container.innerHTML = filtered.map((clip, i) => `
      <div class="clip-item ${i === selectedIndex ? 'selected' : ''} ${clip.pinned ? 'pinned' : ''}"
           data-id="${clip.id}" data-index="${i}"
           ondblclick="App.pasteItem('${clip.id}')">
        <div class="clip-header">
          <div class="clip-meta">
            <span class="clip-lang">${clip.language}</span>
            <span class="clip-time">${formatTime(clip.timestamp)}</span>
            ${clip.pinned ? '<span style="color: var(--pin-color); font-size: 12px;">📌</span>' : ''}
          </div>
          <div class="clip-actions">
            <button class="btn btn-icon" onclick="event.stopPropagation(); App.editItem('${clip.id}')" title="Edit">
              ✏️
            </button>
            <button class="btn btn-icon" onclick="event.stopPropagation(); App.togglePin('${clip.id}')" title="Pin">
              📌
            </button>
            <button class="btn btn-icon" onclick="event.stopPropagation(); App.copyItem('${clip.id}')" title="Copy">
              📋
            </button>
            <button class="btn btn-icon btn-danger" onclick="event.stopPropagation(); App.deleteItem('${clip.id}')" title="Delete">
              ✕
            </button>
          </div>
        </div>
        <div class="clip-preview">${escapeHtml(clip.preview || clip.text)}</div>
      </div>
    `).join('');

    // Add click handlers for selection
    container.querySelectorAll('.clip-item').forEach(el => {
      el.addEventListener('click', () => {
        selectedIndex = parseInt(el.dataset.index);
        renderClips();
      });
    });
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

  function getFilteredClips() {
    return clips.filter(clip => {
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return clip.text.toLowerCase().includes(q) || clip.language.toLowerCase().includes(q);
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
      toast('Pasted to active app');
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
      await pywebview.api.delete_item(id);
      clips = clips.filter(c => c.id !== id);
      if (selectedIndex >= clips.length) selectedIndex = clips.length - 1;
      renderClips();
      toast('Item deleted');
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
  function toast(msg) {
    const el = toastEl();
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 2000);
  }

  // ── Utilities ────────────────────────────────────────────
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

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