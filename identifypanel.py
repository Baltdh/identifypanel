#!/usr/bin/env python3
"""IdentifyPanel: safe offline ROCKNIX panel overlay utility."""
import argparse, hashlib, json, os, platform, shutil, struct, time
from pathlib import Path

MAGIC=b"\xd0\x0d\xfe\xed"
STATE=".identifypanel"

def digest(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def check(p):
    try:
        h=p.read_bytes()[:40]
        if len(h)<8 or h[:4]!=MAGIC: return False,"FDT magic inválido"
        size=struct.unpack(">I",h[4:8])[0]
        if size<40 or size>p.stat().st_size: return False,"tamanho FDT inconsistente"
        return True,f"FDT válido estruturalmente ({size} bytes)"
    except OSError as e: return False,str(e)

def overlay_dir(root):
    for p in (root/"overlays",root/"ROCKNIX"/"overlays"):
        if p.is_dir(): return p
    raise SystemExit("Pasta overlays não encontrada na partição informada.")

def manifest(root):
    p=root/STATE/"manifest.json"
    if p.exists():
        try: return p,json.loads(p.read_text(encoding="utf-8"))
        except Exception: raise SystemExit("Manifesto IdentifyPanel inválido.")
    return p,{"format":1,"history":[],"original_backup":None}

def save(p,m):
    p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(".tmp"); t.write_text(json.dumps(m,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); os.replace(t,p)

def inspect(a):
    root=Path(a.boot).resolve(); od=overlay_dir(root); active=od/"mipi-panel.dtbo"
    print("Partição:",root,"\nOverlays:",od)
    if active.exists():
        ok,msg=check(active); print("Ativo:",ok,msg,"SHA256:",digest(active))
    else: print("Overlay mipi-panel.dtbo ausente.")
    fs=sorted(od.glob("mipi-panel.dtbo.*"))
    print("Alternativos:",len(fs))
    for p in fs:
        ok,msg=check(p); print(("OK" if ok else "INVÁLIDO"),p.name,p.stat().st_size,digest(p),msg)

def profiles(a):
    root=Path(a.profiles)
    fs=sorted(p for p in root.rglob("*") if p.is_file() and (p.suffix==".dtbo" or ".dtbo." in p.name)) if root.exists() else []
    if not fs: print("Nenhum DTBO encontrado. Adicione os binários oficiais verificados."); return
    for p in fs:
        ok,msg=check(p); print(("OK" if ok else "INVÁLIDO"),p,digest(p),msg)

def apply(a):
    root=Path(a.boot).resolve(); src=Path(a.dtbo).resolve()
    if not root.is_dir() or not src.is_file(): raise SystemExit("Caminho da partição ou DTBO não existe.")
    ok,msg=check(src)
    if not ok: raise SystemExit("DTBO recusado: "+msg)
    od=overlay_dir(root); target=od/"mipi-panel.dtbo"; mp,m=manifest(root)
    state=root/STATE; state.mkdir(parents=True,exist_ok=True)
    stamp=time.strftime("%Y%m%d-%H%M%S")
    if target.exists():
        backup=state/("mipi-panel.before-"+stamp+".dtbo"); shutil.copy2(target,backup)
        if not m["original_backup"]: m["original_backup"]=str(backup.relative_to(root))
    tmp=target.with_suffix(".dtbo.new"); shutil.copy2(src,tmp)
    valid,detail=check(tmp)
    if not valid: tmp.unlink(missing_ok=True); raise SystemExit("Cópia temporária inválida: "+detail)
    os.replace(tmp,target)
    m.setdefault("history",[]).append({"time":time.strftime("%Y-%m-%dT%H:%M:%S%z"),"profile":a.name or src.name,"sha256":digest(target),"visual_confirmation":"pending"})
    m["active_profile"]=a.name or src.name; save(mp,m)
    print("Instalado:",target,"\nSHA256:",digest(target))
    print("Desligue com segurança e teste visualmente. O programa não consegue confirmar pixels visíveis.")

def restore(a):
    root=Path(a.boot).resolve(); mp,m=manifest(root); rel=m.get("original_backup")
    if not rel: raise SystemExit("Não há overlay original salvo pelo IdentifyPanel.")
    backup=(root/rel).resolve()
    if root not in backup.parents or not backup.is_file(): raise SystemExit("Backup ausente ou caminho inseguro.")
    ok,msg=check(backup)
    if not ok: raise SystemExit("Backup inválido: "+msg)
    target=overlay_dir(root)/"mipi-panel.dtbo"; tmp=target.with_suffix(".dtbo.restore"); shutil.copy2(backup,tmp)
    if target.exists(): shutil.copy2(target,root/STATE/("before-restore-"+time.strftime("%Y%m%d-%H%M%S")+".dtbo"))
    os.replace(tmp,target); m.setdefault("history",[]).append({"action":"restore-original","sha256":digest(target)})
    m["active_profile"]="original-backup"; save(mp,m); print("Overlay original restaurado:",target)

def device_info(a):
    print("Sistema:",platform.platform())
    for label,p in (("model",Path("/proc/device-tree/model")),("compatible",Path("/proc/device-tree/compatible")),("cpuinfo",Path("/proc/cpuinfo"))):
        if p.exists(): print("\n["+label+"]\n",p.read_bytes().replace(b"\0",b"\n").decode("utf-8","replace")[:10000])
    drm=Path("/sys/class/drm")
    if drm.is_dir():
        print("\n[DRM — diagnóstico, não confirmação visual]")
        for p in sorted(drm.iterdir()):
            s=p/"status"
            if s.is_file():
                try: print(p.name,s.read_text().strip())
                except OSError: pass
    print("\nmodel/compatible identificam placa/SoC; connected não prova que o LCD exibe imagem.")

p=argparse.ArgumentParser(description="Diagnóstico e instalação segura de DTBO ROCKNIX")
s=p.add_subparsers(required=True)
q=s.add_parser("inspect"); q.add_argument("--boot",required=True); q.set_defaults(run=inspect)
q=s.add_parser("profiles"); q.add_argument("--profiles",default="./profiles"); q.set_defaults(run=profiles)
q=s.add_parser("apply"); q.add_argument("--boot",required=True); q.add_argument("--dtbo",required=True); q.add_argument("--name"); q.set_defaults(run=apply)
q=s.add_parser("restore"); q.add_argument("--boot",required=True); q.set_defaults(run=restore)
q=s.add_parser("device-info"); q.set_defaults(run=device_info)
a=p.parse_args(); a.run(a)
