/* Preview preference only. Production reuses catalyst-ui's useThemePreference. */
(() => {
  const storageKey = 'catalyst.design.appearance';
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const normalize = value => ['light', 'dark'].includes(value) ? value : 'system';
  let preference = 'system';
  try { preference = normalize(localStorage.getItem(storageKey)); } catch { /* Use this page's selection when storage is unavailable. */ }

  function apply() {
    document.documentElement.dataset.appearance = preference;
    document.documentElement.dataset.colorMode = preference === 'system'
      ? (media.matches ? 'dark' : 'light') : preference;
    document.querySelectorAll('[data-appearance-choice]').forEach(control => { control.value = preference; });
  }

  // Apply before styles paint; changing appearance never reloads the workspace.
  apply();
  document.addEventListener('DOMContentLoaded', apply);
  document.addEventListener('change', event => {
    if (!event.target.matches('[data-appearance-choice]')) return;
    preference = normalize(event.target.value);
    apply();
    try {
      if (preference === 'system') localStorage.removeItem(storageKey);
      else localStorage.setItem(storageKey, preference);
    } catch { /* The current page still changes; persistence is optional. */ }
  });
  media.addEventListener('change', () => { if (preference === 'system') apply(); });
  // Keep the preview frame and its surrounding controls in the same appearance.
  window.addEventListener('storage', event => {
    if (event.key !== storageKey && event.key !== null) return;
    preference = normalize(event.newValue);
    apply();
  });
})();
