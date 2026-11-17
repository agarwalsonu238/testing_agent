# Designs for the Design reviewer

Export each page's design frame from Figma as PNG at desktop and mobile size, named after the route:

| Route | Files |
|---|---|
| `/` | `home.desktop.png`, `home.mobile.png` |
| `/pricing` | `pricing.desktop.png`, `pricing.mobile.png` |
| `/settings/billing` | `settings-billing.desktop.png`, `settings-billing.mobile.png` |

The Design reviewer compares the running page with these at 1440×900 and 390×844.
Set `DESIGNS_DIR` in `backend/.env` to use another folder.
