import re, sys, cairosvg
src,out,W=sys.argv[1],sys.argv[2],int(sys.argv[3])
s=open(src).read()
cairosvg.svg2png(bytestring=s.encode(),write_to=out,output_width=W)
