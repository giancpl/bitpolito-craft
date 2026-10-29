//! Small BitPolito UI integration; presentation mutations remain engine commands.
use crate::SlideApp;
use egui::{Color32, ColorImage, TextureOptions, Ui};
use serde_json::json;

pub fn starters(app: &mut SlideApp, ui: &mut Ui, query: &str) {
    let q = query.to_lowercase();
    ui.horizontal_wrapped(|ui| {
        for s in deckcraft_engine::bitpolito::starters().into_iter().filter(|s| format!("{} {}", s.name, s.summary).to_lowercase().contains(&q)) {
            if ui.button(&s.name).on_hover_text(&s.summary).clicked() {
                let _ = app.run("file.new", json!({"template":s.id}));
            }
        }
    });
}

pub fn assets(app: &mut SlideApp, ui: &mut Ui) {
    let query_id = ui.scope_id().with("bitpolito-asset-query");
    let mut query = ui.ctx().data_mut(|d| d.get_temp::<String>(query_id).unwrap_or_default());
    ui.label("BitPolito logos and icons");
    ui.text_edit_singleline(&mut query);
    ui.ctx().data_mut(|d| d.insert_temp(query_id, query.clone()));
    let q = query.to_lowercase();
    let available = app.session.active().is_some();
    egui::ScrollArea::vertical().max_height(360.0).show(ui, |ui| {
        for asset in deckcraft_engine::bitpolito::assets().iter().filter(|a| format!("{} {}", a.label, a.category).to_lowercase().contains(&q)) {
            ui.horizontal(|ui| {
                let id = egui::Id::unique(("bitpolito-thumbnail", asset.id));
                let mut texture = ui.ctx().data_mut(|d| d.get_temp::<egui::TextureHandle>(id));
                if texture.is_none()
                    && let Some(image) = deckcraft_render::decode_image(asset.bytes)
                {
                    let image = ColorImage::from_rgba_unmultiplied([image.width() as usize, image.height() as usize], image.as_raw());
                    let t = ui.ctx().load_texture(asset.id, image, TextureOptions::LINEAR);
                    ui.ctx().data_mut(|d| d.insert_temp(id, t.clone()));
                    texture = Some(t);
                }
                if let Some(t) = texture {
                    egui::Frame::new().fill(Color32::from_gray(200)).show(ui, |ui| {
                        ui.add(egui::Image::new(&t).fit_to_exact_size(egui::vec2(76.0, 36.0)));
                    });
                }
                if ui.add_enabled(available, egui::Button::new(asset.label)).clicked() {
                    let _ = app.run("bitpolito.insertAsset", json!({"id":asset.id}));
                    ui.close();
                }
            });
        }
    });
}

/// Browser New defaults to the brand starter; explicit upstream theme/template requests survive.
#[cfg(target_arch = "wasm32")]
pub fn defaults(id: &str, mut params: serde_json::Value) -> serde_json::Value {
    if id == "file.new" && params.get("theme").is_none() && params.get("template").is_none() && params.get("blank").is_none() {
        if !params.is_object() {
            params = json!({});
        }
        let template = deckcraft_model::bitpolito::config().map(|c| c.default_template).unwrap_or_else(|_| "bitpolito-blank".into());
        params["template"] = json!(template);
    }
    params
}
