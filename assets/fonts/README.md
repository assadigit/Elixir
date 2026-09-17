# Inter Font (optional, recommended)

This app is designed to use **Inter** — an open-source typeface that matches
SF Pro's class and renders crisply at the compact 11px body size this UI uses.

## How to enable Inter

1. Download these 4 files from the official Inter release
   (https://github.com/rsms/inter/releases — look for the latest v4 release,
   "Inter-x.x.zip", and extract the `Inter/static/` folder):

   - `Inter-Regular.ttf`
   - `Inter-Medium.ttf`
   - `Inter-SemiBold.ttf`
   - `Inter-Bold.ttf`

   Direct links (replace `4.0` with the latest version if needed):
   - https://github.com/rsms/inter/releases/download/v4.0/Inter-Regular.ttf
   - https://github.com/rsms/inter/releases/download/v4.0/Inter-Medium.ttf
   - https://github.com/rsms/inter/releases/download/v4.0/Inter-SemiBold.ttf
   - https://github.com/rsms/inter/releases/download/v4.0/Inter-Bold.ttf

2. Place the 4 `.ttf` files in **this folder** (`assets/fonts/`).

3. Restart the app.  Inter is auto-detected and registered on startup — no
   settings change needed.

## If you don't install Inter

The app falls back transparently to:

    Segoe UI Variable  →  Segoe UI  →  Helvetica Neue  →  Arial

(Segoe UI Variable is the default on Windows 11; Segoe UI on Windows 10.)
The UI still looks clean and professional — Inter is an enhancement, not a
requirement.
