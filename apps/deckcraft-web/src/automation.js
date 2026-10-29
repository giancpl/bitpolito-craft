// Same-origin, explicitly enabled command bridge for browser regression tests.
const enabled = new URLSearchParams(location.search).has('automation');
const queue = [];
const waiting = new Map();
let sequence = 0;
export function automationReady() {
  if (!enabled) return;
  window.bitpolito = { execute(command, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      waiting.set(id, {resolve, reject});
      queue.push({id, command, params});
      // Wake the canvas event loop even when recovery is disabled or the UI is idle.
      document.getElementById('deckcraft_canvas')?.dispatchEvent(new MouseEvent('mousemove', {
        pointerId: 1, pointerType: 'mouse', clientX: 0, clientY: 0, bubbles: true
      }));
    });
  }};
}
export function automationDrain() { return JSON.stringify(queue.splice(0)); }
export function automationReply(id, raw) {
  const pending = waiting.get(id);
  if (!pending) return;
  waiting.delete(id);
  const response = JSON.parse(raw);
  if (response.error) pending.reject(new Error(response.error));
  else pending.resolve(response.result);
}
