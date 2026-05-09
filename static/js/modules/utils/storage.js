/**
 * Client-side Storage Utilities
 * Uses IndexedDB for offline caching, NOT for auth tokens or sensitive data
 */

window.HF = window.HF || {};

const HFStorage = {
  // IndexedDB database name and version
  DB_NAME: 'HackForge',
  DB_VERSION: 1,
  DB: null,

  // Initialize IndexedDB
  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.DB_NAME, this.DB_VERSION);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.DB = request.result;
        resolve();
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Create object stores
        if (!db.objectStoreNames.contains('cache')) {
          db.createObjectStore('cache', { keyPath: 'key' });
        }
        if (!db.objectStoreNames.contains('drafts')) {
          db.createObjectStore('drafts', { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains('recent')) {
          db.createObjectStore('recent', { keyPath: 'id' });
        }
      };
    });
  },

  // Save to cache
  async saveCache(key, data, ttl = 3600000) {
    if (!this.DB) await this.init();

    return new Promise((resolve, reject) => {
      const store = this.DB.transaction('cache', 'readwrite').objectStore('cache');
      const item = {
        key,
        data,
        expiresAt: Date.now() + ttl
      };

      const request = store.put(item);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  },

  // Get from cache
  async getCache(key) {
    if (!this.DB) await this.init();

    return new Promise((resolve, reject) => {
      const store = this.DB.transaction('cache', 'readonly').objectStore('cache');
      const request = store.get(key);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const item = request.result;
        if (item && item.expiresAt > Date.now()) {
          resolve(item.data);
        } else {
          resolve(null);
          if (item) this.clearCache(key);
        }
      };
    });
  },

  // Clear cache
  async clearCache(key) {
    if (!this.DB) await this.init();

    return new Promise((resolve, reject) => {
      const store = this.DB.transaction('cache', 'readwrite').objectStore('cache');
      const request = store.delete(key);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  },

  // Clear all cache
  async clearAllCache() {
    if (!this.DB) await this.init();

    return new Promise((resolve, reject) => {
      const store = this.DB.transaction('cache', 'readwrite').objectStore('cache');
      const request = store.clear();

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  },

  // Save draft
  async saveDraft(id, content, metadata = {}) {
    if (!this.DB) await this.init();

    return new Promise((resolve, reject) => {
      const store = this.DB.transaction('drafts', 'readwrite').objectStore('drafts');
      const draft = {
        id,
        content,
        metadata,
        savedAt: new Date().toISOString()
      };

      const request = store.put(draft);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(draft);
    });
  },

  // Get draft
  async getDraft(id) {
    if (!this.DB) await this.init();

    return new Promise((resolve, reject) => {
      const store = this.DB.transaction('drafts', 'readonly').objectStore('drafts');
      const request = store.get(id);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result || null);
    });
  },

  // Delete draft
  async deleteDraft(id) {
    if (!this.DB) await this.init();

    return new Promise((resolve, reject) => {
      const store = this.DB.transaction('drafts', 'readwrite').objectStore('drafts');
      const request = store.delete(id);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  },

  // Get all drafts
  async getAllDrafts() {
    if (!this.DB) await this.init();

    return new Promise((resolve, reject) => {
      const store = this.DB.transaction('drafts', 'readonly').objectStore('drafts');
      const request = store.getAll();

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result || []);
    });
  },

  // Save to recent
  async saveRecent(id, data) {
    if (!this.DB) await this.init();

    return new Promise((resolve, reject) => {
      const store = this.DB.transaction('recent', 'readwrite').objectStore('recent');
      const item = {
        id,
        ...data,
        accessedAt: new Date().toISOString()
      };

      const request = store.put(item);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  },

  // Get recent items
  async getRecent(limit = 10) {
    if (!this.DB) await this.init();

    return new Promise((resolve, reject) => {
      const store = this.DB.transaction('recent', 'readonly').objectStore('recent');
      const request = store.getAll();

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const items = request.result || [];
        const sorted = items.sort((a, b) => 
          new Date(b.accessedAt) - new Date(a.accessedAt)
        );
        resolve(sorted.slice(0, limit));
      };
    });
  }
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
  HFStorage.init().catch(err => console.error('Failed to initialize storage:', err));
});

window.HFStorage = HFStorage;
