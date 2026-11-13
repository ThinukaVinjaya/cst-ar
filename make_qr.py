# usage: python3 make_qr.py https://your-site.netlify.app/
import sys, qrcode
url=sys.argv[1]
q=qrcode.QRCode(box_size=20,border=4,error_correction=qrcode.constants.ERROR_CORRECT_H)
q.add_data(url); q.make(fit=True)
q.make_image().save("qr-code.png"); print("saved qr-code.png for",url)
