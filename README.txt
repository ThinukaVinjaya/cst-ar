CST LAN Challenge - Ghost Salute WebAR (Android & iOS)

Overview:
- Built from Gost Salute.fbx into a fast, mobile-ready glTF binary: models/ghost_salute.glb (8.44 MB, down from 29.5 MB FBX).
- Exact tabletop scale (25 cm height) and boots-on-ground alignment (y = 0) baked directly into the mesh, skeleton, and animation data.
- Contains the full Mixamo skeletal "Salute" animation (47 bone channels) and all 13 PBR materials with 12 embedded textures.

How It Works (True 6-DoF World-Anchored AR — Walk 360° Around Ghost):
- Android (Chrome + ARCore WebXR): Preloads models/ghost_salute.glb natively, searches for a real horizontal table surface, snaps Ghost flat onto the table facing you, locks him with an ARCore World Anchor, and stops moving — walk your phone 360° around him!
- iPhone (Safari + Apple AR Quick Look): Uses <model-viewer> native Quick Look with floor/table plane anchoring (6-DoF ARKit) so Ghost locks solidly on the table and you can walk around him.

Files:
- index.html                : Clean WebAR page (<model-viewer> + WebXR 6-DoF table anchoring).
- models/ghost_salute.glb   : Optimized, textured, real-world scaled (25 cm) animated Ghost Salute model.
- tools/build_ghost_salute.py: Rebuilds models/ghost_salute.glb from FBX2glTF output.

Deployment Tip:
- Before uploading to Netlify Drop / GitHub Pages, you can remove the 30 MB source file `Gost Salute.fbx` so only the fast 8.44 MB `models/ghost_salute.glb` is deployed.
- Host on HTTPS (Netlify, Vercel, GitHub Pages), then generate QR code:
  python make_qr.py https://your-hosted-domain/
