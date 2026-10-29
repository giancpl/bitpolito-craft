//! Namespaced brand commands, usable from the editor, CLI, and MCP.
use super::{CommandSpec, always, bad, cmd, has_slide, str_param};
use crate::{Result, Session};
use serde_json::{Value, json};
pub fn specs() -> Vec<CommandSpec> {
    vec![
        cmd!(query "bitpolito.assets", "BitPolito Assets", [], None, "{} → assets", always, list),
        cmd!("bitpolito.insertAsset", "Insert BitPolito Asset", ["Insert", "BitPolito"], None, "{id, rect?: [x,y,w,h]}", has_slide, insert),
    ]
}
fn list(_: &mut Session, _: &Value) -> Result<Value> {
    Ok(json!({"assets":crate::bitpolito::assets().iter().map(|a|json!({"id":a.id,"label":a.label,"category":a.category})).collect::<Vec<_>>()}))
}
fn insert(s: &mut Session, p: &Value) -> Result<Value> {
    let id = str_param(p, "id").ok_or_else(|| bad("bitpolito.insertAsset", "missing id"))?;
    let a = crate::bitpolito::assets().iter().find(|a| a.id == id).ok_or_else(|| bad("bitpolito.insertAsset", "unknown asset"))?;
    let mut args = json!({"data":super::base64_encode(a.bytes),"name":format!("{}.png",a.id)});
    if let Some(rect) = p.get("rect") {
        args["rect"] = rect.clone();
    }
    s.execute("insert.picture", &args)
}
