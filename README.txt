CST LAN Challenge - Animated AR Ghost Operator (Android & iOS)

Overview:
- Single military character ("Ghost") with authentic animated actions (tactical breathing, weapon sway, and head scanning).
- Replaces the 6-soldier ring rotation with a single, standalone animated operator standing in place.
- Android (Chrome + ARCore): Custom WebXR AR with instant camera-front placement, table surface auto-snapping, and interactive Action trigger (Idle / Scan).
- iOS (Safari + ARKit): Apple AR Quick Look fallback with horizontal plane preliminary anchoring (auto-placement) and looping Idle animation via models/ghost_animated.usdz.

Assets:
- models/ghost_animated.glb   : Full 3D model with 13 materials, PBR textures, and Idle/Scan/Spin animations.
- models/ghost_animated.usdz  : Native Apple USDZ package built for iOS Safari AR Quick Look.

Tuning in index.html:
- TARGET_HEIGHT: Set character height in metres (0.25 = 25 cm tabletop action figure; 1.8 = life-size).
- DIST & DROP  : Initial distance ahead of and below the phone camera.

Rebuilding USDZ:
- python tools/build_ghost_usdz.py

Hosting:
- Host the root folder on HTTPS (e.g. Netlify, Vercel, GitHub Pages).
- Generate event QR code: python make_qr.py https://your-hosted-domain/
