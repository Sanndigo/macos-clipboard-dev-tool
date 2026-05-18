const Editor = (() => {
  let _view = null;
  let _isOpen = false;
  let _currentItem = null;

  const panelEl = () => document.getElementById('editor-panel');
  const langLabel = () => document.getElementById('editor-lang');

  // Map our language names to CodeMirror 5 MIME modes
  const LANG_MAP = {
    javascript: 'text/javascript',
    typescript: 'application/typescript',
    python: 'text/x-python',
    html: 'text/html',
    css: 'text/css',
    json: 'application/json',
    sql: 'text/x-sql',
    rust: 'text/x-rustsrc',
    cpp: 'text/x-c++src',
    java: 'text/x-java',
    go: 'text/x-go',
  };

  function open(item) {
    _currentItem = item;
    _isOpen = true;

    const panel = panelEl();
    if (!panel) return;
    panel.classList.remove('hidden');

    if (langLabel()) langLabel().textContent = item.language;

    const editorContainer = document.getElementById('editor-container');
    editorContainer.innerHTML = ''; // clear

    const mode = LANG_MAP[item.language] || 'text/plain';

    _view = CodeMirror(editorContainer, {
      value: item.text,
      mode: mode,
      theme: 'material-darker',
      lineNumbers: true,
      matchBrackets: true,
      indentUnit: 4,
      viewportMargin: Infinity,
    });

    // Focus editor after slight delay so rendering catches up
    setTimeout(() => {
      if (_view) _view.focus();
    }, 50);
  }

  async function save() {
    if (!_currentItem || !_view) return;
    const newText = _view.getValue();
    try {
      await pywebview.api.update_item_text(_currentItem.id, newText);
      if (typeof App !== 'undefined') {
        await App.loadHistory();
        App.toast('Saved!');
      }
      close();
    } catch (e) {
      console.error('Save failed:', e);
    }
  }

  function close() {
    _isOpen = false;
    const panel = panelEl();
    if (panel) panel.classList.add('hidden');
    
    // CodeMirror 5 doesn't need explicit destroy(), just clear DOM
    const editorContainer = document.getElementById('editor-container');
    if (editorContainer) editorContainer.innerHTML = '';
    _view = null;
    _currentItem = null;

    // Return focus to search to prevent WebKit from losing focus and dropping global hotkeys
    setTimeout(() => {
      const search = document.getElementById('search-input');
      if (search) search.focus();
    }, 10);
  }

  function isOpen() {
    return _isOpen;
  }

  return { open, close, save, isOpen };
})();

// Attach globally for inline HTML event handlers (e.g. onclick="Editor.save()")
window.Editor = Editor;
