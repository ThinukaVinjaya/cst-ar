CST LAN Challenge - animated AR soldiers around a physical loot box (AR only)
Android (Chrome + ARCore): custom WebXR AR - squad appears instantly in front of the camera, animated, no scanning, no touch; height auto-snaps to the table when a surface is seen. iPhone: Apple AR Quick Look fallback (movable, usually static). Tune DIST and DROP in index.html.
Rebuild model: cd tools && npm i @gltf-transform/core @gltf-transform/functions && node build_squad.js
  (settings at top: ring radius, soldier height, count). Source character: tools/Soldier.glb (from the three.js examples, a Mixamo character) - check its licence suits your event.
Animations in squad.glb: Patrol (walking round the box, first clip so AR viewers play it) and Guard (idle).
Host the folder on HTTPS (Netlify Drop), then: python3 make_qr.py https://your-link/
