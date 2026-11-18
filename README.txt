CST LAN Challenge - Ghost Salute WebAR (Android & iOS)

Overview:
- All local 3D model files have been removed from the repository.
- Loads the animated FBX model directly from AWS S3:
  https://cst-lan.s3.eu-north-1.amazonaws.com/Gost+Salute.fbx
- Automatically normalizes FBX scale to tabletop size (28 cm), places feet on the ground, and plays the embedded Salute animation.

Cross-Platform AR Support:
- Android (Chrome + ARCore): Native WebXR immersive-ar with instant camera-front placement, automatic table surface height snapping (hit-test), and Recenter / Size controls.
- iOS (iPhone/iPad Safari) & Non-ARCore Android: Live rear-camera WebRTC AR with gyroscope/motion tracking, 1-finger drag placement, 2-finger pinch-to-resize, and full skeletal FBX animation (no USDZ needed, zero "Object could not be opened" errors).

IMPORTANT - AWS S3 Bucket CORS Configuration:
Because mobile browsers fetch the FBX file from S3 using JavaScript, make sure your S3 bucket (`cst-lan`) has CORS enabled under Permissions -> Cross-origin resource sharing (CORS):

[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedOrigins": ["*"],
    "ExposeHeaders": ["Content-Length"]
  }
]

Also ensure public read access (`s3:GetObject`) is enabled for `Gost Salute.fbx`.

Tuning in index.html:
- MODEL_URL     : S3 URL of the FBX model.
- TARGET_HEIGHT : Tabletop character height in metres (0.28 = 28 cm; set to 1.8 for life-size).
- DIST & DROP   : Initial distance ahead of and below the phone camera.

Hosting:
- Host the root folder on HTTPS (e.g. Netlify Drop, Vercel, GitHub Pages) — HTTPS is required for camera & WebXR access on Android and iOS.
- Generate event QR code: python make_qr.py https://your-hosted-domain/

