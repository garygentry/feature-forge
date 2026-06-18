# Vendor-Construct Inventory (fixture)

This is the REQ-VND-03 audit artifact. It documents the vendor construct
`${CLAUDE_PLUGIN_ROOT}` as prose, so it is listed in RESIDUAL_VAR_EXEMPT and must
NOT be flagged by rule 3 even though it lives under a canonical surface.

| Construct | Disposition |
| --- | --- |
| `${CLAUDE_PLUGIN_ROOT}` (canonical) | routed-through-resolver |
| `${CLAUDE_PLUGIN_ROOT}` (forge-root.sh fallback) | preserved-as-spec-allowed |
| `${CLAUDE_PLUGIN_ROOT}` (hooks.json) | out-of-canon |
