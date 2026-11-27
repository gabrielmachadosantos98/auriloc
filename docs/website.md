# Website (landing page)

The landing page lives in [`site/`](../site). It is plain HTML and CSS with no build step.

## Preview locally

```powershell
uv run python -m http.server 8080 -d site
```

Then open http://localhost:8080.

## Live site

https://auriloc.gabrielmachadosantos98.workers.dev/

Deployed on Cloudflare (Workers static assets) from the `site/` folder of this repository.
Every push to `main` redeploys it. Only `site/` is public; the rest of the repository is not
served.

## Configuration

- **Waitlist form:** [Tally](https://tally.so) form `2jPvWD`, set in `TALLY_FORM_ID` near the
  end of `site/index.html`. The ID is the last part of the share link
  (`https://tally.so/r/2jPvWD`).
- **Privacy contact:** the email in `site/privacy.html` ("Your rights").
- **Analytics:** Cloudflare Web Analytics, installed manually with the beacon script at the
  end of each page (`index.html`, `privacy.html`, `acceptable-use.html`). It is cookie-free,
  so no consent banner is needed. The token is public by design. Add the same script to any
  new page. Dashboard: Cloudflare > **Analytics & Logs** > **Web Analytics**.
- **Security headers:** `site/_headers`.

Cloudflare serves `/privacy.html` at `/privacy` (it redirects the `.html` URL), which is
expected.

## Deploying elsewhere

The site is static, so any host works. On Cloudflare Pages, use no build command and `site`
as the output directory; there you can enable Web Analytics from the project's **Metrics**
tab instead of the manual script.
