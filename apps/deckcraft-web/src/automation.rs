//! Opt-in same-origin bridge; executes the same commands as editor controls.
use serde::Deserialize;
use serde_json::{Value, json};
use wasm_bindgen::prelude::*;
#[wasm_bindgen(module = "/src/automation.js")]
extern "C" {
    #[wasm_bindgen(js_name = automationReady)]
    pub fn ready();
    #[wasm_bindgen(js_name = automationDrain)]
    fn drain() -> String;
    #[wasm_bindgen(js_name = automationReply)]
    fn reply(id: u32, result: String);
}
#[derive(Deserialize)]
struct Request {
    id: u32,
    command: String,
    params: Value,
}
pub fn tick(app: &mut deckcraft_ui_egui::SlideApp) {
    let requests: Vec<Request> = serde_json::from_str(&drain()).unwrap_or_default();
    for request in requests {
        let result = match app.run(&request.command, request.params) {
            Ok(result) => json!({"result":result}),
            Err(error) => json!({"error":error}),
        };
        reply(request.id, result.to_string());
    }
}
