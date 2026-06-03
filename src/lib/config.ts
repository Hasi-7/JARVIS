export interface AppSettings {
  vaultPath: string;
  brainCmd:  string;
}

const STORAGE_KEY = 'brain-ui.settings';

// Defaults — will be resolved from backend (brain vault-path, app config)
// once the FastAPI layer is implemented.
export const DEFAULTS: AppSettings = {
  vaultPath: String.raw`D:\Hasnain\Personal\OneDrive - University of Toronto\AI-Command-Center`,
  brainCmd:  String.raw`D:\Hasnain\Personal\bin\brain.cmd`,
};

export function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveSettings(settings: AppSettings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function clearSettings(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function hasLocalSettings(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) !== null;
  } catch {
    return false;
  }
}
