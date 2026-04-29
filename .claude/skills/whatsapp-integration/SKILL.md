---
name: whatsapp-integration
description: Inject a floating WhatsApp chat widget into a client's website, colour-matched to their brand palette. Use when user says "WhatsApp", "widget de WhatsApp", "añadir chat", "botón de WhatsApp", or asks to activate the whatsapp_widget service for a client.
argument-hint: "[client-slug] [phone] [welcome message] [business hours]"
---

# whatsapp-integration

Injects a brand-coloured floating WhatsApp chat button into `output/websites/{slug}/index.html`. Idempotent — safe to run multiple times. Logs service activation to `client_services`.

## When to Invoke

Trigger this skill whenever:
- The user says "añadir WhatsApp", "widget de WhatsApp", "chat de WhatsApp", "integrar WhatsApp", "botón de WhatsApp"
- The user asks to activate or configure the `whatsapp_widget` service for a client
- The user provides a WhatsApp Business number for a client

---

## Workflow

### Step 1 — Validate Client

```python
import sys; sys.path.insert(0, "tools")
import db
client = db.get_client("client-slug")
# Abort if None
```

### Step 2 — Read Client Website

```python
html = Path(f"output/websites/{slug}/index.html").read_text(encoding="utf-8")
```
Abort if file does not exist — website must be built first.

### Step 3 — Extract Primary Brand Color

Regex the `:root { ... }` block. Preference order:
1. `--primary` var
2. `--copper` var (the WAT default)
3. First var containing a 6-digit hex `#[0-9a-fA-F]{6}`
4. Fallback: `#25D366` (WhatsApp green)

### Step 4 — Idempotency Guard

Check for `data-wat-whatsapp` attribute in the HTML. If found, print a warning and exit cleanly — do not inject a second widget.

### Step 5 — Build Widget HTML

```html
<!-- WAT WhatsApp Widget -->
<style>
  .wat-wa-btn {
    position: fixed;
    bottom: 24px;
    right: 24px;   /* or left: 24px if --position=bottom-left */
    z-index: 9999;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: {brand_color};
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 16px {brand_color}55;
    cursor: pointer;
    text-decoration: none;
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .wat-wa-btn:hover { transform: scale(1.1); }
  .wat-wa-btn svg { width: 28px; height: 28px; fill: white; }
  .wat-wa-tooltip {
    position: fixed;
    bottom: 90px;
    right: 24px;
    background: white;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    color: #333;
    box-shadow: 0 2px 12px rgba(0,0,0,0.15);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s ease;
    white-space: nowrap;
    max-width: 220px;
  }
  .wat-wa-btn:hover + .wat-wa-tooltip { opacity: 1; }
</style>
<a
  data-wat-whatsapp="1"
  class="wat-wa-btn"
  href="https://wa.me/{phone_digits_only}?text={url_encoded_message}"
  target="_blank"
  rel="noopener noreferrer"
  aria-label="Contactar por WhatsApp"
>
  <!-- WhatsApp SVG icon -->
  <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
  </svg>
</a>
<div class="wat-wa-tooltip">{hours_text}</div>
<!-- /WAT WhatsApp Widget -->
```

### Step 6 — Inject and Save

Inject the widget HTML immediately before `</body>`. Write the modified HTML back to `output/websites/{slug}/index.html`.

### Step 7 — Log Service Activation

```python
with db._connect() as conn:
    client_id = conn.execute("SELECT id FROM clients WHERE slug=?", (slug,)).fetchone()["id"]
    existing = conn.execute(
        "SELECT id FROM client_services WHERE client_id=? AND service_code='whatsapp_widget'",
        (client_id,)
    ).fetchone()
    if existing:
        conn.execute("UPDATE client_services SET active=1 WHERE id=?", (existing["id"],))
    else:
        conn.execute(
            "INSERT INTO client_services(client_id, service_code, active) VALUES(?,?,1)",
            (client_id, "whatsapp_widget")
        )
```

---

## Arguments

| Arg | Required | Notes |
|---|---|---|
| `--client-slug` | Yes | Must match a client in DB |
| `--phone` | Yes | E.164 format: `+34600000000` |
| `--message` | Yes | Spanish welcome text, URL-encoded in the link |
| `--hours` | Yes | Business hours string shown in tooltip |
| `--position` | No | `bottom-right` (default) or `bottom-left` |

---

## Edge Cases

- **Website not found:** Abort — run `build_website.py` first
- **Double injection:** Detect `data-wat-whatsapp` attribute — skip silently with warning
- **Phone format:** Strip all non-digits except leading `+`, then strip `+` for `wa.me` URL
- **Message encoding:** Use `urllib.parse.quote_plus` for the pre-filled text
