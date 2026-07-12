---
name: testing-static-github-pages-site
description: Test this dependency-free GitHub Pages application locally, including form generation, print output, reset behavior, and responsive layout.
---

# Testing the static site

## Devin Secrets Needed

None.

## Local preview

Run from the repository root:

```bash
python3 -m http.server 4173 --bind 127.0.0.1
```

Open `http://127.0.0.1:4173/` in the existing Chrome session. The app has no backend, authentication, build step, package install, or external API.

## Runtime test procedure

1. Submit the empty form and confirm native required-field validation blocks generation without changing the preview.
2. Fill distinct principal and representative data, choose a non-default authority preset, set a known validity date, and toggle substitution.
3. Generate the document and compare every identifying value, formatted date, authority phrase, substitution status, and signature name against the inputs.
4. Read the complete authority sentence; preset text might be individually correct while producing duplicated or ungrammatical wording when combined with the fixed sentence prefix.
5. Open `Печать / PDF` and confirm print preview contains only the document. The form, site header, toolbar, and disclaimer should be excluded.
6. Reset the form and confirm both input values and generated preview content are cleared.
7. Resize Chrome to roughly 500 px wide and verify the app uses one column and has no horizontal overflow:

```js
document.documentElement.scrollWidth <= document.documentElement.clientWidth
```

## Useful checks

```bash
sed -n '/<script>/,/<\/script>/p' index.html | sed '1d;$d' | node --check -
git diff --check
```

If direct computer typing drops non-Latin characters, use CDP-driven systematic form entry while still performing submit, print, reset, and navigation through the visible UI.

## Expected infrastructure

- There may be no CI workflow; check the PR before assuming checks exist.
- A missing `favicon.ico` can return 404 without affecting application behavior.
- No environment blueprint is required unless testing introduces installed dependencies or tools.
