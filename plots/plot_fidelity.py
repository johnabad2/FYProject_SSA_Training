"""
plot_fidelity.py - the graphs for the detailed-vs-cheap model comparison (fidelity test).

  python plot_fidelity.py [repo folder]        (default: the folder above this script)

Reads   fidelity_test/data/frames_*.csv, pictures_*.npz, run_info.json   (made by fidelity_test.py in Blender)
Writes  fidelity_test/data/summary_stats.json   errors per model and geometry (the numbers quoted)
        fidelity_test/fidelity_main.png          the 2 x 2 figure: brightness curves, error vs triangles, washout
        fidelity_test/fidelity_pictures.png      the same frame at coarser and coarser pixel blocks
Needs Python with numpy and matplotlib.  Run it outside Blender (any Python).

Model names used in the data:  A = detailed Aqua (115k), N4k = plain automatic reduction (4k),
D30k / D10k / D5k / D4k = shape-kept reductions, C = Suomi NPP low-poly (a different satellite).
"""
import csv
import glob
import json
import math
import os
import shutil
import sys
import tempfile

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _write(dest, saver):
    """Save via a temp file, then copy over: writing straight onto an existing file can fail on some mounted drives."""
    tmp = os.path.join(tempfile.gettempdir(), "_plot_tmp_" + os.path.basename(dest))
    saver(tmp)
    shutil.copyfile(tmp, dest)
    os.remove(tmp)


def stats():
    """Error of each cheap model against the detailed one, for each geometry (written to summary_stats.json)."""
    D=os.path.join(ROOT,"fidelity_test","data")+os.sep
    rows=[]
    for f in sorted(glob.glob(D+"frames_*.csv")):
        rows+=list(csv.DictReader(open(f)))
    cfgs=sorted({r["config"] for r in rows})
    vars_=["A","N4k","D30k","D10k","D5k","D4k","C"]
    info=json.load(open(D+"run_info.json"))
    def get(cfg,v,key="flux"):
        rs=[r for r in rows if r["config"]==cfg and r["variant"]==v]
        rs.sort(key=lambda r:int(r["frame"]))
        return np.array([float(r[key]) for r in rs])
    LV=[2**i for i in range(10)]
    out={}
    for cfg in cfgs:
        fa=get(cfg,"A","flux")
        o={"fluxA_max":fa.max(),"fluxA_mean":fa.mean(),"frac_dark":float((fa<0.01*fa.max()).mean())}
        for v in vars_[1:]:
            fv=get(cfg,v,"flux")
            d={}
            d["weighted_err"]=float(np.abs(fv-fa).sum()/fa.sum())
            d["bias"]=float(fv.sum()/fa.sum()-1)
            lit=fa>0.05*fa.max()
            d["max_err_lit"]=float(np.max(np.abs(fv-fa)[lit]/fa[lit]))
            d["r"]=float(np.corrcoef(fa,fv)[0,1])
            # shape error after best constant rescale
            s=(fa*fv).sum()/(fv*fv).sum()
            d["shape_err"]=float(np.abs(s*fv-fa).sum()/fa.sum())
            d["scale"]=float(s)
            if v!="C":
                E=[]
                for k in LV:
                    e=get(cfg,v,f"E_block{k}")
                    E.append(float((e*fa).sum()/fa.sum()))
                d["E"]=E
            o[v]=d
        out[cfg]=o
    json.dump(out,open(D+"summary_stats.json","w"),indent=1)
    for cfg in cfgs:
        print(cfg, "dark frac %.2f"%out[cfg]["frac_dark"])
        for v in vars_[1:]:
            d=out[cfg][v]; print("  %-5s werr %.3f bias %+.3f maxlit %.3f r %.4f shape %.3f"%(v,d["weighted_err"],d["bias"],d["max_err_lit"],d["r"],d["shape_err"]), "E1 %.3f E32 %.3f E128 %.3f E512 %.3f"%(d["E"][0],d["E"][5],d["E"][7],d["E"][9]) if "E" in d else "")
    print(info["variants"])
    return out


def main_figure():
    """fidelity_main.png: curves, error vs triangle count, and the washout with distance."""
    D=os.path.join(ROOT,"fidelity_test","data")+os.sep
    rows=[]
    for f in sorted(glob.glob(D+"frames_*.csv")): rows+=list(csv.DictReader(open(f)))
    st=json.load(open(D+"summary_stats.json")); info=json.load(open(D+"run_info.json"))
    SURF,INK,INK2,GRID="#fcfcfb","#0b0b0b","#52514e","#e6e5e1"
    BLUE,ORANGE,AQUA="#2a78d6","#eb6834","#1baf7a"
    plt.rcParams.update({"font.family":"DejaVu Sans","axes.facecolor":SURF,"figure.facecolor":SURF,
        "axes.edgecolor":GRID,"axes.labelcolor":INK2,"xtick.color":INK2,"ytick.color":INK2,"axes.spines.top":False,"axes.spines.right":False,"font.size":10.5})
    def get(cfg,v,key="flux"):
        rs=sorted([r for r in rows if r["config"]==cfg and r["variant"]==v],key=lambda r:int(r["frame"]))
        return np.array([float(r[key]) for r in rs])
    def grid(ax):
        ax.grid(color=GRID,lw=0.8); ax.set_axisbelow(True)
    def title(ax,t,s):
        ax.set_title(t,loc="left",fontsize=13,fontweight="bold",color=INK,pad=26)
        ax.text(0,1.025,s,transform=ax.transAxes,fontsize=9.8,color=INK2,va="bottom")
    GEO=[("dawn_dusk_pass","dawn-dusk pass"),("spin_phase030","spin, 30°"),("spin_phase090","spin, 90°"),("spin_phase150","spin, 150°")]
    V=info["variants"]
    fig=plt.figure(figsize=(16,9.4))
    gs=fig.add_gridspec(2,2,hspace=0.62,wspace=0.24,left=0.06,right=0.975,top=0.84,bottom=0.075)
    fig.text(0.06,0.955,"Detailed vs cheap satellite model: how much does the brightness curve change?",fontsize=17,fontweight="bold",color=INK)
    fig.text(0.06,0.915,"Same Sun, viewing and spin angles for every model.  Brightness = total light from the satellite, orthographic camera (parallel rays, as at orbital range).  "
             "Detailed = Aqua, 115k triangles.",fontsize=9.8,color=INK2)
    # (a) pass
    ax=fig.add_subplot(gs[0,0]); grid(ax)
    cfg="dawn_dusk_pass"
    tt=[float(r["spin_deg"]) for r in sorted([r for r in rows if r["config"]==cfg and r["variant"]=="A"],key=lambda r:int(r["frame"]))]
    x=np.arange(len(tt))/(len(tt)-1)*497
    ax.plot(x,get(cfg,"A"),color=BLUE,lw=2); ax.plot(x,get(cfg,"D4k"),color=ORANGE,lw=2); ax.plot(x,get(cfg,"N4k"),color=AQUA,lw=2)
    ax.set_xlabel("time into the visible pass (s)"); ax.set_ylabel("brightness (arbitrary units)")
    ax.set_xlim(0,497); ax.set_ylim(0,1450)
    for yy,c,lab in ((1330,BLUE,"detailed (115k triangles)"),(1180,ORANGE,"cheap, shape kept (4.8k)"),(1030,AQUA,"plain automatic reduction (4k)")):
        ax.plot([8,24],[yy+25,yy+25],color=c,lw=2.5); ax.text(30,yy,lab,color=INK,fontsize=10,va="center")
    title(ax,"Dawn-dusk pass: the cheap models get the curve wrong","brightness through one visible pass (48 steps), mostly backlit: the Sun is behind the satellite")
    # (b) spin 90
    ax=fig.add_subplot(gs[0,1]); grid(ax)
    cfg="spin_phase090"
    sp=get(cfg,"A","spin_deg")
    ax.plot(sp,get(cfg,"A"),color=BLUE,lw=2); ax.plot(sp,get(cfg,"D4k"),color=ORANGE,lw=2); ax.plot(sp,get(cfg,"N4k"),color=AQUA,lw=2)
    ax.set_xlim(0,355); ax.set_xticks(range(0,361,60)); ax.set_xlabel("spin angle (degrees)"); ax.set_ylabel("brightness (arbitrary units)")
    ymax=4400; ax.set_ylim(0,ymax)
    for yy,c,lab in ((4150,BLUE,"detailed"),(3850,ORANGE,"cheap, shape kept"),(3550,AQUA,"plain reduction")):
        ax.plot([200,222],[yy,yy],color=c,lw=2.5); ax.text(228,yy,lab,color=INK,fontsize=10,va="center")
    title(ax,"Spinning, Sun 90° from the camera","same peaks, but the cheap models are systematically dimmer")
    # (c) error vs triangles
    ax=fig.add_subplot(gs[1,0]); grid(ax)
    tris=[V[k]["tris"] for k in ("D30k","D10k","D5k","D4k")]
    mk={"dawn_dusk_pass":"o","spin_phase030":"s","spin_phase090":"^","spin_phase150":"D"}
    for cfg,lab in GEO:
        e=[st[cfg][k]["weighted_err"]*100 for k in ("D30k","D10k","D5k","D4k")]
        ax.plot(tris,e,color=ORANGE,lw=1.6,marker=mk[cfg],ms=6,mfc=ORANGE,mec=SURF)
        ax.plot([V["N4k"]["tris"]],[st[cfg]["N4k"]["weighted_err"]*100],marker=mk[cfg],ms=7,mfc=AQUA,mec=SURF,ls="")
        ax.text(tris[0]*1.12,e[0]+{"spin_phase030":1.5,"spin_phase090":-1.0,"spin_phase150":-1.0}.get(cfg,0),lab,fontsize=9.5,color=INK,va="center")
    ax.set_xscale("log"); ax.set_xlim(3300,75000); ax.minorticks_off()
    ax.set_xticks([4000,5000,10000,30000]); ax.set_xticklabels(["4k","5k","10k","30k"])
    ax.set_xlabel("triangles in the cheap model (detailed = 115k)"); ax.set_ylabel("brightness error at a point source (%)")
    ax.set_ylim(0,112)
    ax.text(3400,106,"orange: shape kept     teal: plain automatic reduction (4k)     spin lines: Sun-camera angle",fontsize=9,color=INK2)
    title(ax,"Fewer triangles, bigger error","average |cheap − detailed| ÷ detailed over the whole spin / pass")
    # (d) washout
    ax=fig.add_subplot(gs[1,1]); grid(ax)
    ks=[2**i for i in range(10)]
    for cfg,lab in GEO:
        E=np.array(st[cfg]["D4k"]["E"])*100
        ax.plot(ks,E,color=ORANGE,lw=1.6,marker=mk[cfg],ms=5,mfc=ORANGE,mec=SURF)
        ax.text(ks[-1]*1.12,E[-1],lab,fontsize=9.5,color=INK,va="center")
    ax.axvspan(128,512,color="#eaeaf5",alpha=0.6,lw=0)
    ax.text(1.1,62,"shaded: orbital range. A 1″-per-pixel sensor at 1,300–2,200 km\nsums the light over blocks of ~160–270 px; coarser sensors\nsee a single point (512).",fontsize=9,color=INK2,va="center")
    ax.set_xscale("log",base=2); ax.set_xticks(ks); ax.set_xticklabels([str(k) for k in ks]); ax.set_xlim(0.8,2600)
    ax.set_xlabel("pixel block the light is added over (1 = full detail, 512 = a single point)"); ax.set_ylabel("brightness error (%)")
    ax.set_ylim(0,125)
    title(ax,"Washout: part of the error disappears with distance, not all","cheap model (4.8k, shape kept) vs detailed; coarser blocks = further away")
    out_png=os.path.join(ROOT,"fidelity_test","fidelity_main.png")
    _write(out_png, lambda p: fig.savefig(p,dpi=130,facecolor=SURF)); plt.close(fig)
    print("saved",out_png)


def pictures():
    """fidelity_pictures.png: one frame shown at coarser and coarser pixel blocks."""
    D=os.path.join(ROOT,"fidelity_test","data")+os.sep
    SURF,INK,INK2="#fcfcfb","#0b0b0b","#52514e"
    z=np.load(D+"pictures_spin_phase090.npz")
    names=list(z["names"]); idx=int(z["idx"][0])      # brightest frame
    A=z["A_0"][0].astype(float); NB=z["N4k_1"][0].astype(float); DB=z["D4k_2"][0].astype(float)
    rows=[r for r in csv.DictReader(open(D+"frames_spin_phase090.csv")) if int(r["frame"])==idx]
    E={r["variant"]:[float(r[f"E_block{k}"]) for k in (1,8,32,128,512)] for r in rows}
    ks=[1,8,32,128,512]
    def binned(L,k):
        n=L.shape[0]//k; return L.reshape(n,k,n,k).sum(axis=(1,3))
    # crop to the satellite for clarity
    ys,xs=np.where(A>0); y0,y1,x0,x1=ys.min(),ys.max()+1,xs.min(),xs.max()+1
    c=max(y1-y0,x1-x0); cy,cx=(y0+y1)//2,(x0+x1)//2
    y0=max(0,min(512-c,cy-c//2)); x0=max(0,min(512-c,cx-c//2))
    fig,axs=plt.subplots(3,5,figsize=(15,9.2),facecolor=SURF)
    fig.subplots_adjust(left=0.09,right=0.99,top=0.82,bottom=0.03,wspace=0.06,hspace=0.28)
    fig.text(0.02,0.955,"Fine detail washes out as the satellite gets further away",fontsize=17,fontweight="bold",color=INK)
    fig.text(0.02,0.915,"Spin 90° geometry, brightest frame.  Each column adds the light over bigger pixel blocks (a coarser sensor or a larger range); brightness shared across a row.\n"
      "Under each picture: brightness error vs the detailed model at that block size.",fontsize=10,color=INK2,va="top")
    labs=[("Detailed (115k)",A,None),("Cheap, shape kept (4.8k)",DB,"D4k"),("Plain reduction (4k)",NB,"N4k")]
    for r,(lab,img,key) in enumerate(labs):
        for c_,k in enumerate(ks):
            ax=axs[r,c_]; ax.axis("off")
            def view(im):
                b=binned(im,k)
                if k<=32:
                    n=max(1,c//k); by=min(b.shape[0]-n,y0//k); bx=min(b.shape[1]-n,x0//k)
                    return b[by:by+n,bx:bx+n]
                return b
            im2=view(img); vmax=view(A).max()
            ax.imshow(np.clip(im2/vmax,0,1)**0.5,cmap="gray",interpolation="nearest",vmin=0,vmax=1)
            if r==0: ax.set_title("every pixel" if k==1 else ("whole picture = 1 pixel" if k==512 else f"{k}×{k} px blocks"),fontsize=11,color=INK)
            if key: ax.text(0.5,-0.04,f"error {E[key][c_]*100:.0f}%",transform=ax.transAxes,ha="center",va="top",fontsize=10.5,color=INK)
        axs[r,0].text(-0.06,0.5,lab,transform=axs[r,0].transAxes,rotation=90,ha="right",va="center",fontsize=11,fontweight="bold",color=INK)
    out_png=os.path.join(ROOT,"fidelity_test","fidelity_pictures.png")
    _write(out_png, lambda p: fig.savefig(p,dpi=110,facecolor=SURF)); plt.close(fig)
    print("saved",out_png)


if __name__ == "__main__":
    stats()
    main_figure()
    pictures()
