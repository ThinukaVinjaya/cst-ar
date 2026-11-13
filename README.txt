CST LAN Challenge - Call of Duty 4 Military AR Diorama (Android & iOS)

Overview:
- Designed to augment a real-world physical table decoration item (centerpiece / loot box / trophy) placed on the table.
- The center (radius ~20 cm on the real table) is kept completely clear for the real physical item.
- Ghost and authentic Call of Duty 4 military items form a tactical fortified perimeter encircling the centerpiece:
  1. Ghost (Simon Riley): Stands at the perimeter, performing an automatic continuous 8.5s combat loop (idle breathing, raising rifle, 3-round burst fire with recoil, perimeter scan).
  2. M18A1 Claymore Mine: With scissor wire tripod legs and "FRONT TOWARD ENEMY" stenciling guarding the front approach.
  3. 7.62mm NATO Ammo Crates & Cans: Heavy military crates and ammo cans with metal latches and military stenciling.
  4. CoD4 Intel Tactical Laptop: Open military Toughbook terminal resting on an equipment case with a glowing green UAV radar display.
  5. Curved Sandbag Fortification: Multi-tier burlap sandbag barricade securing the right flank.
  6. C4 Demolition Charge: Explosive block with black tape, wires, and digital receiver with red active LED.
  7. Tactical Supply Drop Crate: Reinforced military equipment container on the left flank.

Platform Compatibility:
- Android (Chrome + ARCore): Custom WebXR AR with instant camera-front placement and automatic table surface height snapping.
- iPhone (Safari + ARKit): Fully 64-byte aligned Apple USDZ with preliminary horizontal plane anchoring (auto-places on the table with zero tapping).

Files:
- index.html                   : WebAR frontend with WebXR, Three.js, and <model-viewer>.
- models/ghost_animated.glb    : Complete 3D diorama with Ghost's combat loop and military perimeter props.
- models/ghost_animated.usdz   : Strictly 64-byte aligned Apple USDZ package for iPhone.
- tools/build_military_props.py: Builds all 3D props, textures, and updates both GLB and USDZ.
- tools/optimize_and_animate.py: Generates Ghost's tactical combat sequence.
- tools/build_ghost_usdz.py    : Compliant 64-byte aligned USDZ packager for iOS.

Rebuilding:
- python tools/build_military_props.py

Hosting:
- Host the root folder on HTTPS (e.g. Netlify Drop, Vercel, GitHub Pages).
- Generate event QR code: python make_qr.py https://your-hosted-domain/
