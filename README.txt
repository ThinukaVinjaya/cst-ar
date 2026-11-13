CST LAN Challenge - Animated AR Ghost Operator (Android & iOS)

Overview:
- Standalone animated military operator ("Ghost") with rich military action animations:
  1. Idle   - Combat breathing, weapon sway, hand micro-movements.
  2. Aim    - Weapon raised to eye-level sights, cheek weld, combat lean.
  3. Fire   - 3-round tactical burst with realistic recoil kick, muzzle climb, and recovery.
  4. Reload - Magazine drop, fresh mag insertion bump, bolt rack, and return to ready.
  5. Scan   - 90-degree tactical sector sweep with coordinated weapon tracking.

Optimization & Fast Loading:
- models/ghost_animated.glb: Vertex buffer optimized by removing redundant attribute streams (saving ~2.8 MB) and pruning unused textures, loading ~50% faster on mobile networks.
- Asynchronous preloader in index.html fetches the model during page render so AR opens immediately on tap.
- Interactive action buttons in both the 2D preview and AR camera overlay for instant move triggering.

Files:
- index.html                   : WebAR frontend with WebXR, Three.js, <model-viewer>, and action switcher.
- models/ghost_animated.glb    : Optimized 3D model with 5 military animations.
- models/ghost_animated.usdz   : Native Apple USDZ with preliminary horizontal plane anchoring for iPhone.
- tools/optimize_and_animate.py: Re-packs GLB and generates the 5 action animation tracks.
- tools/build_ghost_usdz.py    : Re-builds the USDZ package for iOS Quick Look.

Tuning in index.html:
- TARGET_HEIGHT: Set character height in metres (0.25 = 25 cm tabletop action figure; 1.8 = life-size).
- DIST & DROP  : Initial distance ahead of and below the phone camera.

Rebuilding:
- python tools/optimize_and_animate.py
- python tools/build_ghost_usdz.py

Hosting:
- Host the root folder on HTTPS (e.g. Netlify Drop, Vercel, GitHub Pages).
- Generate event QR code: python make_qr.py https://your-hosted-domain/
