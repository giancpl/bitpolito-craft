//! Versioned BitPolito branding. This module is the only model integration point.
use deckcraft_color::{ColorScheme, Rgba};
use serde::Deserialize;

use crate::theme::{FontScheme, FontSet, Theme, default_format};

#[derive(Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Config {
    pub title: String,
    pub brand_version: String,
    pub accent: String,
    pub dark_accent: String,
    pub font: String,
    pub default_template: String,
}

pub const CONFIG: &str = include_str!("../../../brand/bitpolito/config.json");

pub fn config() -> Result<Config, serde_json::Error> {
    serde_json::from_str(CONFIG)
}

pub fn accent(dark: bool) -> Rgba {
    let c = config().ok();
    let hex = c.as_ref().map(|c| if dark { c.dark_accent.as_str() } else { c.accent.as_str() });
    hex.and_then(Rgba::from_hex).unwrap_or(Rgba::rgb(0, 28, 224))
}

pub fn theme() -> Theme {
    let font = config().map(|c| c.font).unwrap_or_else(|_| "Inter".into());
    let mut colors = [Rgba::WHITE; 12];
    for (slot, hex) in colors
        .iter_mut()
        .zip(["10163A", "FFFFFF", "536080", "EEF0FF", "001CE0", "536080", "00A896", "F2B134", "C94C66", "7986CB", "001CE0", "536080"])
    {
        *slot = Rgba::from_hex(hex).unwrap_or(Rgba::BLACK);
    }
    if let Ok(tokens) = serde_json::from_str::<serde_json::Value>(include_str!("../../../brand/bitpolito/tokens.json")) {
        for (slot, key) in colors.iter_mut().take(4).zip(["text", "background", "muted", "surface"]) {
            if let Some(value) = tokens.get("colors").and_then(|c| c.get(key)).and_then(|v| v.as_str()).and_then(Rgba::from_hex) {
                *slot = value;
            }
        }
    }
    if let Some(slot) = colors.get_mut(4) {
        *slot = accent(false);
    }
    Theme {
        name: "BitPolito".into(),
        colors: ColorScheme { name: "BitPolito".into(), colors },
        fonts: FontScheme {
            name: "BitPolito".into(),
            major: FontSet { latin: font.clone(), ..Default::default() },
            minor: FontSet { latin: font, ..Default::default() },
        },
        format: default_format(),
        raw_extra: None,
    }
}
