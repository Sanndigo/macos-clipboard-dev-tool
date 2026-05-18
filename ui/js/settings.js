/**
 * Liquid Glass Clipboard Manager — Settings Panel Logic
 */

const Settings = (() => {
  let _settings = {};

  async function load() {
    try {
      _settings = await pywebview.api.get_settings();
    } catch (e) {
      _settings = {};
      console.error('Failed to load settings:', e);
    }
    render();
  }

  function render() {
    // Blur intensity
    const blurSlider = document.getElementById('setting-blur');
    const blurValue = document.getElementById('setting-blur-value');
    if (blurSlider) {
      blurSlider.value = _settings.blur_intensity || 20;
      if (blurValue) blurValue.textContent = `${blurSlider.value}px`;
    }

    // Opacity
    const opacitySlider = document.getElementById('setting-opacity');
    const opacityValue = document.getElementById('setting-opacity-value');
    if (opacitySlider) {
      opacitySlider.value = Math.round((_settings.window_opacity || 0.92) * 100);
      if (opacityValue) opacityValue.textContent = `${opacitySlider.value}%`;
    }

    // Auto-trim
    const trimToggle = document.getElementById('setting-trim');
    if (trimToggle) trimToggle.checked = _settings.auto_trim_whitespace !== false;

    // Theme
    const themeSelect = document.getElementById('setting-theme');
    if (themeSelect) themeSelect.value = _settings.theme || 'auto';

    // Hotkey display
    const hotkeyDisplay = document.getElementById('setting-hotkey');
    if (hotkeyDisplay) {
      const mods = (_settings.hotkey_modifiers || ['option']).map(m => m.charAt(0).toUpperCase() + m.slice(1));
      const key = (_settings.hotkey_key || 'v').toUpperCase();
      hotkeyDisplay.textContent = `${mods.join(' + ')} + ${key}`;
    }

    // Max history
    const maxInput = document.getElementById('setting-max-history');
    if (maxInput) maxInput.value = _settings.max_history || 50;
  }

  async function updateSetting(key, value) {
    _settings[key] = value;
    try {
      await pywebview.api.update_settings({ [key]: value });
    } catch (e) {
      console.error('Failed to update setting:', e);
    }

    // Apply live changes
    if (key === 'blur_intensity') {
      document.documentElement.style.setProperty('--blur-intensity', `${value}px`);
      const label = document.getElementById('setting-blur-value');
      if (label) label.textContent = `${value}px`;
    }
    if (key === 'window_opacity') {
      document.documentElement.style.setProperty('--window-opacity', value);
      const label = document.getElementById('setting-opacity-value');
      if (label) label.textContent = `${Math.round(value * 100)}%`;
    }
    if (key === 'theme') {
      if (value === 'auto') {
        const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
      } else {
        document.documentElement.setAttribute('data-theme', value);
      }
    }
  }

  let recordingHotkey = false;

  function bindEvents() {
    // Blur slider
    document.addEventListener('input', (e) => {
      if (e.target.id === 'setting-blur') {
        updateSetting('blur_intensity', parseInt(e.target.value));
      }
      if (e.target.id === 'setting-opacity') {
        updateSetting('window_opacity', parseInt(e.target.value) / 100);
      }
      if (e.target.id === 'setting-max-history') {
        updateSetting('max_history', parseInt(e.target.value));
      }
    });

    document.addEventListener('change', (e) => {
      if (e.target.id === 'setting-trim') {
        updateSetting('auto_trim_whitespace', e.target.checked);
      }
      if (e.target.id === 'setting-theme') {
        updateSetting('theme', e.target.value);
      }
    });

    const hotkeyDisplay = document.getElementById('setting-hotkey');
    if (hotkeyDisplay) {
      hotkeyDisplay.addEventListener('click', () => {
        recordingHotkey = true;
        hotkeyDisplay.textContent = 'Listening...';
        hotkeyDisplay.style.color = 'var(--accent-color)';
      });

      document.addEventListener('keydown', (e) => {
        if (!recordingHotkey) return;
        e.preventDefault();
        e.stopPropagation();

        if (e.key === 'Escape') {
          recordingHotkey = false;
          hotkeyDisplay.style.color = '';
          render();
          return;
        }

        // Ignore if only a modifier is pressed
        if (['Meta', 'Shift', 'Alt', 'Control'].includes(e.key)) return;

        const mods = [];
        if (e.metaKey) mods.push('command');
        if (e.altKey) mods.push('option');
        if (e.ctrlKey) mods.push('control');
        if (e.shiftKey) mods.push('shift');

        // Extract physical key regardless of keyboard layout (Russian/English)
        let key = e.code;
        if (key.startsWith('Key')) key = key.slice(3).toLowerCase();
        else if (key.startsWith('Digit')) key = key.slice(5);
        else if (key === 'Space') key = 'space';
        else key = e.key.toLowerCase(); // Fallback for special keys

        if (mods.length === 0) return; // Disallow keys without modifiers

        recordingHotkey = false;
        hotkeyDisplay.style.color = '';

        updateSetting('hotkey_modifiers', mods);
        updateSetting('hotkey_key', key);
        render();
      }, true); // Capture phase to prevent bubbling to global listeners
    }
  }

  // Init event bindings once
  document.addEventListener('DOMContentLoaded', bindEvents);

  return { load, updateSetting };
})();
