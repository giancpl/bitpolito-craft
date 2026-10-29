// IndexedDB owns recoverable native documents; a Web Lock owns each browser session.
// No credentials, network, or document contents are sent outside this origin.
let database;
let ownedId;
function request(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error('IndexedDB request failed'));
  });
}
function transaction(mode, operation) {
  return new Promise((resolve, reject) => {
    const tx = database.transaction('sessions', mode);
    operation(tx.objectStore('sessions'));
    tx.oncomplete = () => resolve();
    tx.onerror = tx.onabort = () => reject(tx.error || new Error('Draft transaction failed'));
  });
}
async function claim(id) {
  // Held until the page context is destroyed, including reload and tab/browser closure.
  return new Promise((resolve, reject) => {
    navigator.locks.request('bitpolito-draft-' + id, { ifAvailable: true }, lock => {
      resolve(Boolean(lock));
      if (lock) return new Promise(() => {});
    }).catch(reject);
  });
}
export async function recoveryInit() {
  if (!globalThis.indexedDB || !navigator.locks) throw new Error('This browser cannot provide isolated draft recovery');
  const open = indexedDB.open('bitpolito-craft-recovery', 1);
  open.onupgradeneeded = () => open.result.createObjectStore('sessions', { keyPath: 'id' });
  database = await request(open);
  database.onversionchange = () => database.close();
  const records = await request(database.transaction('sessions').objectStore('sessions').getAll());
  const previous = sessionStorage.getItem('bitpolito-session');
  const ordered = records.sort((a,b) => Number(b.updated) - Number(a.updated));
  if (previous) ordered.sort((a,b) => Number(b.id === previous) - Number(a.id === previous));
  for (const record of ordered) {
    if (await claim(record.id)) {
      ownedId = record.id;
      sessionStorage.setItem('bitpolito-session', ownedId);
      return record.snapshot;
    }
  }
  ownedId = crypto.randomUUID();
  if (!await claim(ownedId)) throw new Error('Could not isolate this tab’s recovery session');
  sessionStorage.setItem('bitpolito-session', ownedId);
  return '';
}
export function recoverySave(snapshot) {
  // IndexedDB serializes overlapping read/write transactions in creation order.
  // Enqueue synchronously: a pagehide event must not defer this work to a microtask.
  try {
    if (!database || !ownedId) throw new Error('Draft storage is unavailable');
    const parsed = JSON.parse(snapshot);
    return transaction('readwrite', store => {
      if (parsed.documents.length) store.put({id: ownedId, updated: Date.now(), snapshot});
      else store.delete(ownedId);
    });
  } catch (error) { return Promise.reject(error); }
}

let flushError = '';
export function recoveryInstallFlush(callback) {
  const flush = () => {
    try {
      const snapshot = callback();
      if (snapshot) recoverySave(snapshot).catch(error => { flushError = String(error); });
    } catch (error) { flushError = String(error); }
  };
  document.addEventListener('visibilitychange', () => { if (document.hidden) flush(); });
  window.addEventListener('pagehide', flush);
}
export function recoveryTakeError() {
  const error = flushError;
  flushError = '';
  return error;
}
