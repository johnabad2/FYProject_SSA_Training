"""make_sun_sweep_media.py - contact sheets and a video from the renders made by sun_sweep.py.
Runs on any machine with Python, Pillow, matplotlib, numpy and ffmpeg:  python make_sun_sweep_media.py <renders_sun_sweep folder>"""
import csv, os, sys, shutil, tempfile, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
D=(sys.argv[1] if len(sys.argv)>1 else ".").rstrip("/\\")+os.sep
OUT=D
path=list(csv.DictReader(open(D+"sun_path.csv")))
SURF,INK,INK2,GRID="#fcfcfb","#0b0b0b","#52514e","#e6e5e1"
A,B=1.6,1.0
FD=os.path.join(matplotlib.get_data_path(),"fonts","ttf")
F=lambda s:ImageFont.truetype(os.path.join(FD,"DejaVuSans.ttf"),s)
FB=lambda s:ImageFont.truetype(os.path.join(FD,"DejaVuSans-Bold.ttf"),s)
def img(model,t): return Image.open(D+f"{model}_sun{int(t):03d}.png").convert("RGB")
def label(r):
    el=float(r["sun_el"]); 
    where="overhead" if el>85 else "underneath" if el<-85 else "level with it" if abs(el)<1 else ("above" if el>0 else "below")
    el=0.0 if abs(el)<0.5 else el
    return f"Sun elevation {el:+.0f}° ({where})   Sun-camera angle {float(r['phase_deg']):.0f}°"
def diagram(t_deg,size=(520,360),dpi=100):
    fig=plt.figure(figsize=(size[0]/dpi,size[1]/dpi),dpi=dpi,facecolor=SURF); ax=fig.add_axes([0.04,0.04,0.92,0.84]); ax.set_facecolor(SURF)
    th=np.linspace(0,2*np.pi,300); ax.plot(A*np.sin(th),B*np.cos(th),color="#b9b8b0",lw=1.6)
    for r in path:
        tt=np.radians(float(r["ellipse_deg"])); ax.plot(A*np.sin(tt),B*np.cos(tt),"o",ms=3,color="#b9b8b0")
    ax.plot(0,0,"s",ms=11,color="#2a78d6"); ax.text(0,-0.2,"satellite",ha="center",va="top",fontsize=9,color=INK2)
    t=np.radians(t_deg); x,y=A*np.sin(t),B*np.cos(t)
    ax.annotate("",xy=(x*0.28,y*0.28),xytext=(x,y),arrowprops=dict(arrowstyle="-|>",color="#eda100",lw=1.6))
    ax.plot(x,y,"o",ms=15,color="#eda100",mec=INK,mew=0.8); ax.text(x,y,"Sun",ha="center",va="center",fontsize=6.5,color=INK)
    ax.text(0,B+0.28,"start: straight overhead",ha="center",fontsize=8.5,color=INK2); ax.text(0,-B-0.34,"passes underneath",ha="center",fontsize=8.5,color=INK2)
    ax.set_xlim(-A-0.5,A+0.5); ax.set_ylim(-B-0.55,B+0.5); ax.set_aspect("equal"); ax.axis("off")
    fig.text(0.04,0.93,"Where the Sun is (side view of its path)",fontsize=10.5,fontweight="bold",color=INK)
    fig.canvas.draw(); im=Image.frombuffer("RGBA",fig.canvas.get_width_height(),fig.canvas.buffer_rgba()).convert("RGB"); plt.close(fig); return im
# ---- contact sheets (every 30 deg)
sel=[r for r in path if int(r["ellipse_deg"])%30==0]
names={"Aqua_detailed":"Aqua, detailed (115k triangles)","SuomiNPP_lowpoly":"Suomi NPP, low-poly (4k triangles)"}
W,H=480,270
for model,title in names.items():
    cols,rows=4,3
    sheet=Image.new("RGB",(cols*W,rows*(H+34)+86),(252,252,251)); d=ImageDraw.Draw(sheet)
    d.text((16,12),f"Sun moving round a fixed satellite on an ellipse: {title}",font=FB(20),fill=(11,11,11))
    d.text((16,46),"Satellite and camera never move. Sun starts overhead (top-left), goes down one side, passes underneath, and comes up the other side.",font=F(13),fill=(82,81,78))
    for k,r in enumerate(sel):
        x,y=(k%cols)*W,86+(k//cols)*(H+34)
        sheet.paste(img(model,r["ellipse_deg"]).resize((W,H),Image.LANCZOS),(x,y))
        d.text((x+6,y+H+4),f"{k+1}. {label(r)}",font=F(11),fill=(11,11,11))
    sheet.save(os.path.join(OUT,f"sheet_{model}.png"))
# ---- video frames (both satellites + diagram)
VF=tempfile.mkdtemp()
for k,r in enumerate(path):
    c=Image.new("RGB",(1280,720+60),(252,252,251)); d=ImageDraw.Draw(c)
    for j,(model,title) in enumerate(names.items()):
        c.paste(img(model,r["ellipse_deg"]).resize((640,360),Image.LANCZOS),(j*640,0)); d.text((j*640+10,8),title,font=FB(16),fill=(255,255,255))
    c.paste(diagram(float(r["ellipse_deg"]),(640,360)),(0,360))
    d.text((680,400),"Fixed satellite, fixed camera.",font=FB(22),fill=(11,11,11))
    d.text((680,440),"Only the Sun moves, round an ellipse:",font=F(18),fill=(82,81,78))
    d.text((680,466),"overhead → down one side → underneath → back up.",font=F(18),fill=(82,81,78))
    d.text((680,520),f"Sun position {int(r['ellipse_deg'])}° round the ellipse",font=F(18),fill=(11,11,11))
    d.text((680,550),label(r).split("   ")[0],font=F(18),fill=(11,11,11)); d.text((680,580),label(r).split("   ")[1],font=F(18),fill=(11,11,11))
    d.text((12,790),"Brightness is as rendered (no exposure change between frames).",font=F(13),fill=(82,81,78))
    c.save(os.path.join(VF,f"f{k:03d}.png"))
subprocess.run(["ffmpeg","-y","-loglevel","error","-framerate","6","-i",os.path.join(VF,"f%03d.png"),"-c:v","libx264","-pix_fmt","yuv420p","-crf","20",os.path.join(OUT,"sun_sweep.mp4")],check=True)
shutil.rmtree(VF)
print("video", round(os.path.getsize(os.path.join(OUT,"sun_sweep.mp4"))/1e6,2),"MB")
