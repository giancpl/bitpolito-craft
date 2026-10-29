//! Browser-local draft snapshots, independent of file downloads and native recovery.
use deckcraft_engine::{DocState, Session};
use deckcraft_ui_egui::SlideApp;
use serde::{Deserialize, Serialize};
use std::cell::RefCell;
use std::rc::Rc;
use std::sync::Arc;
use std::time::Duration;
use wasm_bindgen::JsCast;
use wasm_bindgen::prelude::*;

#[wasm_bindgen(module = "/src/recovery.js")]
extern "C" {
    #[wasm_bindgen(catch, js_name = recoveryInit)]
    async fn init() -> Result<JsValue, JsValue>;
    #[wasm_bindgen(catch, js_name = recoverySave)]
    async fn save(snapshot: String) -> Result<JsValue, JsValue>;
    #[wasm_bindgen(js_name = recoveryInstallFlush)]
    fn install_flush(callback: &js_sys::Function);
    #[wasm_bindgen(js_name = recoveryTakeError)]
    fn take_error() -> String;
}
fn message(error: JsValue) -> String {
    js_sys::Reflect::get(&error, &JsValue::from_str("message"))
        .ok()
        .and_then(|value| value.as_string())
        .or_else(|| error.as_string())
        .unwrap_or_else(|| "Browser storage is unavailable".into())
}
#[derive(Serialize, Deserialize)]
struct Draft {
    name: String,
    data: String,
}
#[derive(Serialize, Deserialize)]
struct Snapshot {
    version: u32,
    active: Option<usize>,
    documents: Vec<Draft>,
}

pub async fn restore(session: &mut Session) -> Result<bool, String> {
    let raw = init().await.map_err(message)?.as_string().unwrap_or_default();
    if raw.is_empty() {
        return Ok(false);
    }
    let snapshot: Snapshot = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    if snapshot.version != 1 {
        return Err("Unsupported draft version; stored drafts were preserved".into());
    }
    // Decode all documents before changing the session. Corrupt snapshots must stay recoverable.
    let docs = snapshot
        .documents
        .into_iter()
        .map(|d| {
            let bytes = deckcraft_engine::cmd::base64_decode(&d.data).ok_or_else(|| "Invalid draft encoding".to_string())?;
            let doc = deckcraft_engine::cmd::file::open_presentation("draft.deckcraft", &bytes).map_err(|e| e.to_string())?;
            let mut restored = DocState::new(doc, None, d.name);
            restored.saved_doc = std::sync::Arc::new((*restored.doc).clone());
            Ok(restored)
        })
        .collect::<Result<Vec<_>, String>>()?;
    for d in docs {
        session.add_document(d);
    }
    if let Some(active) = snapshot.active {
        session.set_active(active);
    }
    Ok(!session.documents().is_empty())
}
#[derive(Default)]
struct Capture {
    documents: Vec<(Arc<deckcraft_engine::model::Presentation>, String)>,
    active: Option<usize>,
}
fn serialize(capture: &Capture) -> Result<String, String> {
    let documents = capture
        .documents
        .iter()
        .map(|(doc, name)| {
            deckcraft_engine::cmd::file::save_bytes(doc, "deckcraft")
                .map(|bytes| Draft { name: name.clone(), data: deckcraft_engine::cmd::base64_encode(&bytes) })
                .map_err(|e| e.to_string())
        })
        .collect::<Result<Vec<_>, _>>()?;
    serde_json::to_string(&Snapshot { version: 1, active: capture.active, documents }).map_err(|e| e.to_string())
}
#[derive(Default)]
pub struct Recovery {
    next: f64,
    fingerprint: Vec<(u64, u64, String)>,
    active: Option<usize>,
    result: Rc<RefCell<Option<Result<(), String>>>>,
    pending: bool,
    capture: Rc<RefCell<Capture>>,
    flush: Option<Closure<dyn FnMut() -> Result<String, JsValue>>>,
    pub disabled: bool,
    pub error: Option<String>,
}
impl Recovery {
    pub fn tick(&mut self, app: &mut SlideApp, ctx: &egui::Context) {
        if self.disabled {
            return;
        }
        // Keep cheap Arc snapshots current even between timed saves. A visibility/pagehide
        // callback can serialize them synchronously before requestAnimationFrame is suspended.
        *self.capture.borrow_mut() =
            Capture { documents: app.session.documents().iter().map(|d| (d.doc.clone(), d.title())).collect(), active: app.session.active_index() };
        if self.flush.is_none() {
            let capture = self.capture.clone();
            let callback = Closure::wrap(
                Box::new(move || serialize(&capture.borrow()).map_err(|e| JsValue::from_str(&e))) as Box<dyn FnMut() -> Result<String, JsValue>>
            );
            install_flush(callback.as_ref().unchecked_ref());
            self.flush = Some(callback);
        }
        let flush_error = take_error();
        if !flush_error.is_empty() {
            self.error = Some(format!("Draft recovery failed: {flush_error}. Download your work to keep it."));
        }
        let result = self.result.borrow_mut().take();
        if let Some(result) = result {
            self.pending = false;
            if let Err(e) = result {
                self.fingerprint.clear();
                self.error = Some(format!("Draft recovery failed: {e}. Download your work to keep it."));
            }
        }
        let now = ctx.input(|i| i.time);
        ctx.request_repaint_after(Duration::from_secs(1));
        let fingerprint = app.session.documents().iter().map(|d| (d.uid, d.revision, d.title())).collect::<Vec<_>>();
        let closed = self.fingerprint.iter().any(|(uid, _, _)| !fingerprint.iter().any(|(other, _, _)| uid == other));
        if self.pending || (!closed && now < self.next) {
            return;
        }
        self.next = now + 5.0;
        let active = app.session.active_index();
        if fingerprint == self.fingerprint && active == self.active {
            return;
        }
        let snapshot = serialize(&self.capture.borrow());
        match snapshot {
            Ok(snapshot) => {
                self.fingerprint = fingerprint;
                self.active = active;
                self.pending = true;
                let result = self.result.clone();
                let ctx = ctx.clone();
                wasm_bindgen_futures::spawn_local(async move {
                    let saved = save(snapshot).await.map(|_| ()).map_err(message);
                    *result.borrow_mut() = Some(saved);
                    ctx.request_repaint();
                });
            }
            Err(e) => {
                self.error = Some(format!("Draft recovery failed: {e}. Download your work to keep it."));
            }
        }
    }
}
