// Where the access token survives a reload. Browser storage can throw (private windows, blocked site
// data), so every access is wrapped and the app still works for the current tab without it.

export interface TokenStorage {
  read: () => string | null;
  write: (token: string) => void;
  clear: () => void;
}

const TOKEN_KEY = 'shibutzim.token';

export function createLocalTokenStorage(): TokenStorage {
  return {
    read: () => {
      try {
        return window.localStorage.getItem(TOKEN_KEY);
      } catch {
        return null;
      }
    },
    write: (token) => {
      try {
        window.localStorage.setItem(TOKEN_KEY, token);
      } catch {
        // Not persisted; the session lasts until the tab closes.
      }
    },
    clear: () => {
      try {
        window.localStorage.removeItem(TOKEN_KEY);
      } catch {
        // Nothing to clear.
      }
    },
  };
}

/** For tests: the same contract, no browser. */
export function createMemoryTokenStorage(initial: string | null = null): TokenStorage {
  let token = initial;
  return {
    read: () => token,
    write: (next) => {
      token = next;
    },
    clear: () => {
      token = null;
    },
  };
}
