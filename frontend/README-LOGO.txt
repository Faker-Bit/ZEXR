ZEXR Deal Hub - logo asset
==========================

Drop the exported brand artwork here as a PNG:

    frontend/public/logo.png

Referenced by:
  - src/components/site/logo.tsx  ->  <LogoImage />   (full artwork)
  - src/app/icon.svg             ->  app icon / favicon (already set to the Z mark)

Recommended: 512x512 or 1024x1024 PNG, square, dark background.

Until logo.png exists the header renders an inline SVG "Z" mark
(<ZexrMark />), so nothing appears broken. After adding the file,
restart the dev server to see it.
