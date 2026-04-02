class InMemoryCache {
  constructor() {
    this.store = new Map();
  }

  get(key) {
    const item = this.store.get(key);
    if (!item) {
      return undefined;
    }
    if (item.expiresAt <= Date.now()) {
      this.store.delete(key);
      return undefined;
    }
    return item.value;
  }

  set(key, value, ttlMs) {
    const expiresAt = Date.now() + Math.max(0, Number(ttlMs) || 0);
    this.store.set(key, { value, expiresAt });
  }

  deleteByPrefix(prefix) {
    for (const key of this.store.keys()) {
      if (key.startsWith(prefix)) {
        this.store.delete(key);
      }
    }
  }
}

export const cache = new InMemoryCache();
