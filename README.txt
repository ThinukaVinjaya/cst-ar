CST LAN Challenge - Ghost Salute WebAR (Android & iOS)

Overview:
- All local 3D model files have been removed from the repository.
- Loads the animated FBX model directly from AWS S3:
  https://cst-lan.s3.eu-north-1.amazonaws.com/Gost+Salute.fbx
- Automatically normalizes FBX scale to tabletop size (25 cm) with boots flush on the table (y = 0) and plays the embedded Salute animation.

How It Works (True 6-DoF World-Anchored AR — Walk 360° Around the Object):
1. Load Model: Downloads Gost+Salute.fbx from S3 and converts it in-memory to GLB for <model-viewer> 3D preview & iOS Quick Look.
2. Search Table:
   - Android (Chrome + ARCore WebXR): Scans for a real horizontal table plane with an orange surface ring.
   - iPhone (Safari + ARKit Quick Look): Uses Apple AR Quick Look's native horizontal table plane detection.
3. Appear & Lock to Table:
   - Once the table surface is detected, Ghost appears solidly anchored to the real table (using an ARCore World Anchor on Android / ARKit plane anchor on iOS).
   - The model stays fixed in place and does NOT move — you can walk your phone 360° all around the object on the table.

Optional Animated iOS Quick Look:
- Apple AR Quick Look's browser-generated USDZ keeps Ghost anchored in 6-DoF AR on the table (usually static pose). If you also upload a pre-baked animated .usdz to S3, set IOS_USDZ_URL in index.html to enable skeletal animation in iPhone Quick Look too.

IMPORTANT - AWS S3 Bucket CORS Configuration:
Ensure your S3 bucket (`cst-lan`) allows public GET and has this CORS rule:

[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedOrigins": ["*"],
    "ExposeHeaders": ["Content-Length"]
  }
]

Hosting:
- Host the root folder on HTTPS (e.g. Netlify Drop, Vercel, GitHub Pages).
- Generate event QR code: python make_qr.py https://your-hosted-domain/
