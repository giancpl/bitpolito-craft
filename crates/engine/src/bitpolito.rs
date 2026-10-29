//! BitPolito templates and assets. Upstream integration is limited to the registries.
use crate::{EngineError, Result};
use deckcraft_geom::{Size, Xfrm};
use deckcraft_model::text::{Anchor, AutoFit, BodyProps, Bullet, LevelStyle, ListStyle, ParaProps, RunProps, TextBody};
use deckcraft_model::{
    Background, ColorRef, Fill, Layout, LayoutId, LayoutType, PhType, Placeholder, Presentation, Shape, ShapeId, ShapeKind, defaults,
};
use serde::Deserialize;
use std::sync::Arc;

#[derive(Clone, Deserialize)]
pub struct PlaceholderDef {
    pub role: String,
    pub rect: [f64; 4],
    pub size: f64,
    pub bold: bool,
    pub text: String,
    pub color: String,
}
#[derive(Clone, Deserialize)]
pub struct LayoutDef {
    pub id: String,
    pub label: String,
    pub background: String,
    pub placeholders: Vec<PlaceholderDef>,
    #[serde(default)]
    pub decorations: Vec<Decoration>,
}
#[derive(Clone, Deserialize)]
pub struct Decoration {
    pub asset: String,
    pub rect: [f64; 4],
}
#[derive(Clone, Deserialize)]
pub struct Starter {
    pub id: String,
    pub name: String,
    pub summary: String,
    pub layouts: Vec<String>,
}
#[derive(Deserialize)]
pub struct Pack {
    pub layouts: Vec<LayoutDef>,
    pub starters: Vec<Starter>,
}

pub fn pack() -> Result<Pack> {
    serde_json::from_str(include_str!("../../../brand/bitpolito/templates.json")).map_err(|e| EngineError::Other(format!("BitPolito package: {e}")))
}
pub fn starters() -> Vec<Starter> {
    pack().map(|p| p.starters).unwrap_or_default()
}
pub fn find(name: &str) -> Option<Starter> {
    starters().into_iter().find(|s| s.id.eq_ignore_ascii_case(name) || s.name.eq_ignore_ascii_case(name))
}
fn color(hex: &str) -> Result<ColorRef> {
    deckcraft_color::Rgba::from_hex(hex).map(ColorRef::rgb).ok_or_else(|| EngineError::Other(format!("Invalid BitPolito color {hex}")))
}
fn id(doc: &mut Presentation) -> Result<u32> {
    doc.alloc_id().ok_or_else(|| EngineError::Other("No document IDs available".into()))
}

/// Create every native master/layout first; starter text belongs to slides and stays editable.
pub fn build(name: &str, size: Size) -> Result<Presentation> {
    let pack = pack()?;
    let starter = find(name).ok_or_else(|| EngineError::Other(format!("Unknown BitPolito starter {name}")))?;
    let mut doc = defaults::blank_presentation(size, deckcraft_model::bitpolito::theme(), false);
    let sx = size.width / 960.0;
    let sy = size.height / 540.0;
    let mut layouts = Vec::new();
    for def in &pack.layouts {
        let mut shapes = Vec::new();
        for (index, field) in def.placeholders.iter().enumerate() {
            if field.rect.iter().any(|v| !v.is_finite())
                || field.rect[2] <= 0.0
                || field.rect[3] <= 0.0
                || !field.size.is_finite()
                || field.size <= 0.0
            {
                return Err(EngineError::Other(format!("Invalid geometry in {}", def.id)));
            }
            let kind = match field.role.as_str() {
                "title" => PhType::Title,
                "subtitle" => PhType::SubTitle,
                _ => PhType::Body,
            };
            let mut style = ListStyle::default();
            style.set(
                0,
                LevelStyle {
                    para: ParaProps { bullet: Some(Bullet::None), margin_left: Some(0.0), indent: Some(0.0), ..Default::default() },
                    run: RunProps {
                        size: Some(field.size * sy),
                        bold: Some(field.bold),
                        font: Some("Inter".into()),
                        fill: Some(Fill::solid(color(&field.color)?)),
                        ..Default::default()
                    },
                },
            );
            let [x, y, w, h] = field.rect;
            shapes.push(Shape {
                id: ShapeId(id(&mut doc)?),
                name: format!("{} {}", field.role, index),
                xfrm: Some(Xfrm::new(x * sx, y * sy, w * sx, h * sy)),
                ph: Some(Placeholder { kind, idx: index as u32, ..Default::default() }),
                text: Some(TextBody {
                    body: BodyProps {
                        anchor: Some(Anchor::Top),
                        autofit: Some(AutoFit::Shrink { font_scale: Some(1.0), line_reduction: 0.0 }),
                        ..Default::default()
                    },
                    list_style: style,
                    ..Default::default()
                }),
                ..Default::default()
            });
        }
        let bg = deckcraft_color::Rgba::from_hex(&def.background).unwrap_or(deckcraft_color::Rgba::WHITE);
        let dark = (bg.r as u32 * 299 + bg.g as u32 * 587 + bg.b as u32 * 114) < 128_000;
        let logo = if dark { "logo-white" } else { "logo-blue" };
        if let Some(asset) = assets().iter().find(|a| a.id == logo) {
            let media = doc
                .add_media(&format!("{}.png", asset.id), "image/png", asset.bytes.to_vec())
                .ok_or_else(|| EngineError::Other("Cannot add BitPolito logo".into()))?;
            shapes.push(Shape {
                id: ShapeId(id(&mut doc)?),
                name: "BitPolito logo".into(),
                xfrm: Some(Xfrm::new(60.0 * sx, 485.0 * sy, 140.0 * sx, 31.0 * sy)),
                kind: ShapeKind::Picture { fill: deckcraft_model::style::PictureFill { media, ..Default::default() } },
                descr: "BitPolito".into(),
                ..Default::default()
            });
        }
        for decoration in &def.decorations {
            let asset = assets()
                .iter()
                .find(|a| a.id == decoration.asset)
                .ok_or_else(|| EngineError::Other(format!("Missing decoration {}", decoration.asset)))?;
            let media = doc
                .add_media(&format!("{}.png", asset.id), "image/png", asset.bytes.to_vec())
                .ok_or_else(|| EngineError::Other("Cannot add decoration".into()))?;
            let [x, y, w, h] = decoration.rect;
            shapes.push(Shape {
                id: ShapeId(id(&mut doc)?),
                name: asset.label.into(),
                xfrm: Some(Xfrm::new(x * sx, y * sy, w * sx, h * sy)),
                kind: ShapeKind::Picture { fill: deckcraft_model::style::PictureFill { media, ..Default::default() } },
                descr: asset.label.into(),
                ..Default::default()
            });
        }
        layouts.push(Layout {
            id: LayoutId(id(&mut doc)?),
            name: def.label.clone(),
            kind: LayoutType::Custom,
            shapes,
            background: Some(Background::Fill { fill: Fill::solid(color(&def.background)?) }),
            show_master_shapes: false,
            preserve: true,
            ..Default::default()
        });
    }
    if let Some(master) = doc.masters.first_mut() {
        Arc::make_mut(master).layouts = layouts;
    }
    for name in &starter.layouts {
        let index = pack.layouts.iter().position(|l| l.id == *name).ok_or_else(|| EngineError::Other(format!("Missing layout {name}")))?;
        let layout = doc.masters.first().and_then(|m| m.layouts.get(index)).ok_or_else(|| EngineError::Other("Missing branded master".into()))?.id;
        let mut slide = defaults::new_slide(&mut doc, layout).ok_or_else(|| EngineError::Other("Cannot create branded slide".into()))?;
        if let Some(def) = pack.layouts.get(index) {
            for (shape, field) in slide.shapes.iter_mut().zip(&def.placeholders) {
                shape.text = Some(TextBody::from_text(&field.text));
            }
        }
        doc.slides.push(Arc::new(slide));
    }
    doc.props.company = "BitPolito".into();
    Ok(doc)
}

pub struct Asset {
    pub id: &'static str,
    pub label: &'static str,
    pub category: &'static str,
    pub bytes: &'static [u8],
}
include!("../../../brand/bitpolito/runtime/registry.rs");
pub fn assets() -> &'static [Asset] {
    ASSETS
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Session;
    use serde_json::json;
    #[test]
    fn starters_keep_editable_layouts_through_both_file_formats() {
        for starter in starters() {
            let doc = build(&starter.id, defaults::WIDE).unwrap();
            assert!(doc.validate().is_empty(), "{:?}", doc.validate());
            assert_eq!(doc.masters[0].layouts.len(), 8);
            assert!(doc.slides.iter().all(|s| s.shapes.iter().any(|s| s.text.is_some())));
            let native = deckcraft_format::load(&deckcraft_format::save(&doc).unwrap()).unwrap();
            let pptx = deckcraft_pptx::import(&deckcraft_pptx::export(&doc).unwrap()).unwrap();
            for back in [&native, &pptx] {
                assert_eq!(back.slides.len(), doc.slides.len());
                assert_eq!(back.slides[0].title(), doc.slides[0].title());
            }
            assert!(!crate::pdf::export(&doc, &Default::default()).unwrap().is_empty());
        }
    }
    #[test]
    fn asset_insertion_undo_and_formats() {
        let mut s = Session::new();
        s.execute("file.new", &json!({"template":"bitpolito-blank"})).unwrap();
        let before = s.doc().unwrap().doc.slides[0].shapes.len();
        s.execute("bitpolito.insertAsset", &json!({"id":"bull"})).unwrap();
        assert_eq!(s.doc().unwrap().doc.slides[0].shapes.len(), before + 1);
        let doc = &s.doc().unwrap().doc;
        let native = deckcraft_format::load(&deckcraft_format::save(doc).unwrap()).unwrap();
        let pptx = deckcraft_pptx::import(&deckcraft_pptx::export(doc).unwrap()).unwrap();
        let bull = assets().iter().find(|asset| asset.id == "bull").unwrap();
        for back in [&native, &pptx] {
            assert_eq!(back.slides[0].shapes.len(), before + 1);
            let ShapeKind::Picture { fill } = &back.slides[0].shapes.last().unwrap().kind else {
                panic!("Inserted asset must remain a native picture after reopening");
            };
            assert_eq!(back.media(fill.media).unwrap().data.as_slice(), bull.bytes);
        }
        s.execute("edit.undo", &json!({})).unwrap();
        assert_eq!(s.doc().unwrap().doc.slides[0].shapes.len(), before);
        assert!(s.execute("bitpolito.insertAsset", &json!({"id":"missing"})).is_err());
    }
}
