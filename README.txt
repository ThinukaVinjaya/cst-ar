CST LAN Challenge - animated AR soldiers around a physical loot box
Two modes (chosen on the first screen):
  Instant view : opens the camera immediately, no table detection; squad floats ~55 cm ahead and stays in place using the phone gyroscope.
  Table AR     : phone's native AR (Android Scene Viewer / iOS Quick Look) locks the squad on the table.
Animations: Patrol (walking around the box) and Guard (standing). Change ring size/height/count at top of make_squad.py, then: python3 make_squad.py
Host the folder on HTTPS (Netlify Drop), then: python3 make_qr.py https://your-link/
