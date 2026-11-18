CST LAN Challenge - Ghost Salute WebAR (Android & iOS)

Overview:
- Loads the animated FBX directly from AWS S3:
  https://cst-lan.s3.eu-north-1.amazonaws.com/Gost+Salute.fbx
- Automatically fixes the Mixamo/FBX GLTF_SceneRootNode 90-degree bindMatrix bug, sanitizes bone names so all 47 Salute animation tracks export and play cleanly, normalizes height to 25 cm tabletop size, and aligns boots flush on y = 0.

Cross-Platform 6-DoF AR (Walk 360° Around Ghost):
- Android (Chrome + ARCore WebXR): Plays the full 47-bone Salute animation directly from the S3 FBX, scans for a real horizontal table surface, snaps Ghost upright onto the table facing you, locks him with a persistent ARCore World Anchor, and stops moving — walk 360° around him!
- iPhone (Safari + Apple AR Quick Look): Uses <model-viewer> native Quick Look with horizontal table plane anchoring. Automatically attaches models/ghost_salute.usdz (64-byte aligned UsdSkel Salute animation) when present so iPhone AR Quick Look plays the full Salute animation too.

Hosting:
- Host on HTTPS (Netlify, Vercel, GitHub Pages) — required for mobile camera & WebXR.
- Generate QR code: python make_qr.py https://your-hosted-domain/
