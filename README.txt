CST LAN Challenge - Animated AR Ghost Operator (Android & iOS)

Overview:
- Single animated military operator ("Ghost") performing an automatic continuous military action loop:
  1. Tactical Combat Idle & breathing (0.0s - 2.0s)
  2. Weapon Raise & Target Lock (2.0s - 3.5s)
  3. 3-Round Burst Fire with weapon recoil kickback & muzzle climb (3.5s - 5.0s)
  4. Perimeter Sector Sweep checking for threats (5.0s - 7.0s)
  5. Tactical Recovery back to ready stance (7.0s - 8.5s)
- Plays automatically without needing any buttons or manual selections.

iOS AR Quick Look Compatibility:
- models/ghost_animated.usdz is strictly 64-byte aligned with the official 0x1986 USDZ padding tag. This resolves the Apple AR Quick Look "Object could not be opened" error.

Android WebXR Compatibility:
- models/ghost_animated.glb is optimized down to ~8.0 MB with clean geometry and PBR materials.
- Instant camera-front placement with automatic tabletop height snapping.

Files:
- index.html                   : WebAR frontend with WebXR, Three.js, <model-viewer>.
- models/ghost_animated.glb    : Optimized 3D model with automatic "Action" loop.
- models/ghost_animated.usdz   : Strictly 64-byte aligned Apple USDZ package for iPhone.
- tools/optimize_and_animate.py: Builds the optimized GLB and Action animation.
- tools/build_ghost_usdz.py    : Builds the 64-byte aligned USDZ package for iOS.

Tuning in index.html:
- TARGET_HEIGHT: Set character height in metres (0.25 = 25 cm tabletop action figure; 1.8 = life-size).
- DIST & DROP  : Initial distance ahead of and below the phone camera.

Rebuilding:
- python tools/optimize_and_animate.py
- python tools/build_ghost_usdz.py

Hosting:
- Host the root folder on HTTPS (e.g. Netlify Drop, Vercel, GitHub Pages).
- Generate event QR code: python make_qr.py https://your-hosted-domain/
