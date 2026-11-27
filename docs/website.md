# Website (landing page)

The landing page lives in [`site/`](../site). It is plain HTML and CSS with no build step.

## Preview locally

```powershell
uv run python -m http.server 8080 -d site
```

Then open http://localhost:8080.

## Before publishing

1. **Waitlist form:** create the form on [Tally](https://tally.so) and paste its ID into
   `TALLY_FORM_ID` near the end of `site/index.html`. The ID is the last part of the share
   link: `https://tally.so/r/wMd8xE` -> `wMd8xE`. Suggested questions:
   - Email (required)
   - Your role: mobile developer / QA / product / other
   - What kind of app do you work on? (delivery, mobility, fitness, ...)
   - How do you test location on iPhone today?
   - Do you use Windows, macOS or both?
2. **Contact email:** replace `CONTACT_EMAIL` in `site/privacy.html` with the address that
   answers privacy requests.

## Deploy to Cloudflare Pages

1. In the Cloudflare dashboard, go to **Workers & Pages** > **Create** > **Pages** >
   **Connect to Git**, and authorize access to the `auriloc` repository.
2. Build settings:
   - Framework preset: **None**
   - Build command: *(leave empty)*
   - Build output directory: **`site`**
3. Deploy. The site is published at `https://<project>.pages.dev` and redeploys on every
   push to `main`.
4. In the Pages project, open **Metrics** and enable **Web Analytics** (cookie-free, no
   banner needed).
5. Optional: add a custom domain under **Custom domains**.

`site/_headers` sets basic security headers on Cloudflare Pages.
