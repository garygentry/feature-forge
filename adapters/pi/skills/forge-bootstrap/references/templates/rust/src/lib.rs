//! Library root for the scaffolded baseline.

/// Returns the project greeting for `name`.
#[must_use]
pub fn greet(name: &str) -> String {
    format!("Hello from {name}")
}
