CST LAN Challenge - animated AR soldiers around a physical loot box (AR only)
Scan QR -> tap "Open AR camera" -> point at the loot box, hold steady: the squad places itself (no touching needed). Android: Scene Viewer (Chrome). iOS: AR Quick Look (Safari). No app needed.
Rebuild model: cd tools && npm i @gltf-transform/core @gltf-transform/functions && node build_squad.js
  (settings at top: ring radius, soldier height, count). Source character: tools/Soldier.glb (from the three.js examples, a Mixamo character) - check its licence suits your event.
Animations in squad.glb: Patrol (walking round the box, first clip so AR viewers play it) and Guard (idle).
Host the folder on HTTPS (Netlify Drop), then: python3 make_qr.py https://your-link/
