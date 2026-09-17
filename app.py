import os,json,secrets,time,uuid,subprocess,base64,tarfile,io
from pathlib import Path
from urllib.parse import quote
from flask import Flask,render_template,request,jsonify,session,redirect,Response
from werkzeug.security import generate_password_hash,check_password_hash

HOME=Path(os.getenv("CLOUDNODE_HOME","/etc/cloudnode-panel"))
STATE=HOME/"state.json"; CONF=HOME/"panel.json"
XRAY=Path(os.getenv("XRAY_CONFIG","/usr/local/etc/xray/config.json"))
SERVICE=os.getenv("XRAY_SERVICE","xray")
app=Flask(__name__)
app.secret_key=os.getenv("CLOUDNODE_SECRET",secrets.token_hex(32))

def init():
    HOME.mkdir(parents=True,exist_ok=True)
    if not CONF.exists():
        CONF.write_text(json.dumps({"user":"admin","password":generate_password_hash(os.getenv("CLOUDNODE_PASSWORD","change-me-now")),"sub_token":secrets.token_urlsafe(24)}))
        os.chmod(CONF,0o600)
    else:
        c=json.loads(CONF.read_text())
        if "sub_token" not in c:
            c["sub_token"]=secrets.token_urlsafe(24); wr(CONF,c)
    if not STATE.exists():
        STATE.write_text('{"nodes":[]}'); os.chmod(STATE,0o600)

def rd(p): init(); return json.loads(p.read_text())
def wr(p,o):
    t=p.with_suffix(".tmp"); t.write_text(json.dumps(o,ensure_ascii=False,indent=2)); os.chmod(t,0o600); t.replace(p)
def auth(): return bool(session.get("ok"))
def running():
    return subprocess.run(["systemctl","is-active",SERVICE],capture_output=True,text=True).stdout.strip()=="active"
def unit_active(name):
    return subprocess.run(["systemctl","is-active",name],capture_output=True,text=True).stdout.strip()=="active"
def bbr_status():
    p=subprocess.run(["sysctl","-n","net.ipv4.tcp_congestion_control"],capture_output=True,text=True)
    return p.stdout.strip() if p.returncode==0 else "unknown"
def node_link(n):
    params=f"encryption=none&type=xhttp&path={quote(n['path'])}&security=none"
    return f"vless://{n['uuid']}@{n['host']}:{n['port']}?{params}#{quote(n['name'])}"
def find_node(st,nid):
    return next((n for n in st["nodes"] if n["id"]==nid),None)

def build(nodes):
    ins=[]
    for n in nodes:
        if n.get("enabled",True):
            ins.append({
              "tag":"cloudnode-"+n["id"],"listen":"0.0.0.0","port":n["port"],"protocol":"vless",
              "settings":{"clients":[{"id":n["uuid"],"email":n["name"]}],"decryption":"none"},
              "streamSettings":{"network":"xhttp","security":"none","xhttpSettings":{"path":n["path"],"mode":"auto"}}
            })
    return {"log":{"loglevel":"warning"},"inbounds":ins,
            "outbounds":[{"protocol":"freedom","tag":"direct"},{"protocol":"blackhole","tag":"blocked"}]}

def apply_config():
    cfg=build(rd(STATE)["nodes"])
    XRAY.parent.mkdir(parents=True,exist_ok=True)
    tmp=XRAY.with_suffix(".cloudnode.tmp")
    tmp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2))
    p=subprocess.run(["xray","run","-test","-config",str(tmp)],capture_output=True,text=True)
    if p.returncode:
        tmp.unlink(missing_ok=True); raise RuntimeError((p.stderr or p.stdout).strip())
    tmp.replace(XRAY)
    p=subprocess.run(["systemctl","restart",SERVICE],capture_output=True,text=True)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout).strip())

@app.route("/login",methods=["GET","POST"])
def login():
    init(); err=""
    if request.method=="POST":
        c=rd(CONF)
        if request.form.get("user")==c["user"] and check_password_hash(c["password"],request.form.get("password","")):
            session["ok"]=True; return redirect("/")
        err="用户名或密码错误"
    return render_template("login.html",err=err)

@app.get("/logout")
def logout(): session.clear(); return redirect("/login")

@app.get("/")
def home(): return render_template("index.html") if auth() else redirect("/login")

@app.get("/api/state")
def state():
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    c=rd(CONF)
    return jsonify(ok=True,running=running(),nodes=rd(STATE)["nodes"],version="0.3.0-beta",
                   sub_url="/sub/"+c["sub_token"],bbr=bbr_status(),caddy=unit_active("caddy"))

@app.post("/api/nodes")
def create():
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    d=request.get_json(force=True)
    name=str(d.get("name","")).strip(); host=str(d.get("host","")).strip()
    try: port=int(d.get("port",443))
    except ValueError: return jsonify(ok=False,error="端口格式错误"),400
    if not name or not host or not 1<=port<=65535:
        return jsonify(ok=False,error="请检查名称、域名/IP和端口"),400
    st=rd(STATE)
    if any(n["port"]==port for n in st["nodes"]):
        return jsonify(ok=False,error="该端口已被 CloudNode 节点使用"),409
    n={"id":secrets.token_hex(4),"name":name[:32],"host":host[:253],"port":port,
       "uuid":str(uuid.uuid4()),"path":"/"+secrets.token_urlsafe(9),
       "enabled":True,"created":int(time.time())}
    st["nodes"].append(n); wr(STATE,st)
    try: apply_config()
    except Exception as e:
        st["nodes"]=[x for x in st["nodes"] if x["id"]!=n["id"]]; wr(STATE,st)
        return jsonify(ok=False,error=str(e)),500
    return jsonify(ok=True,node=n)

@app.delete("/api/nodes/<nid>")
def delete(nid):
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    st=rd(STATE); old=st["nodes"][:]; st["nodes"]=[n for n in old if n["id"]!=nid]
    if len(old)==len(st["nodes"]): return jsonify(ok=False,error="节点不存在"),404
    wr(STATE,st)
    try: apply_config()
    except Exception as e:
        wr(STATE,{"nodes":old}); return jsonify(ok=False,error=str(e)),500
    return jsonify(ok=True)

@app.put("/api/nodes/<nid>")
def update(nid):
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    d=request.get_json(force=True)
    st=rd(STATE); old=json.loads(json.dumps(st)); n=find_node(st,nid)
    if not n: return jsonify(ok=False,error="节点不存在"),404
    name=str(d.get("name",n["name"])).strip(); host=str(d.get("host",n["host"])).strip()
    try: port=int(d.get("port",n["port"]))
    except ValueError: return jsonify(ok=False,error="端口格式错误"),400
    enabled=bool(d.get("enabled",n.get("enabled",True)))
    if not name or not host or not 1<=port<=65535:
        return jsonify(ok=False,error="请检查名称、域名/IP和端口"),400
    if any(x["id"]!=nid and x["port"]==port for x in st["nodes"]):
        return jsonify(ok=False,error="该端口已被 CloudNode 节点使用"),409
    n.update({"name":name[:32],"host":host[:253],"port":port,"enabled":enabled})
    wr(STATE,st)
    try: apply_config()
    except Exception as e:
        wr(STATE,old); return jsonify(ok=False,error=str(e)),500
    return jsonify(ok=True,node=n)

@app.get("/api/nodes/<nid>/link")
def link(nid):
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    n=find_node(rd(STATE),nid)
    if not n: return jsonify(ok=False,error="节点不存在"),404
    return jsonify(ok=True,link=node_link(n))

@app.get("/api/nodes/<nid>/qr")
def qr(nid):
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    n=find_node(rd(STATE),nid)
    if not n: return jsonify(ok=False,error="节点不存在"),404
    try:
        import qrcode
        import qrcode.image.svg
        img=qrcode.make(node_link(n),image_factory=qrcode.image.svg.SvgPathImage)
        buf=io.BytesIO(); img.save(buf)
        return Response(buf.getvalue(),mimetype="image/svg+xml")
    except Exception as e:
        return jsonify(ok=False,error="二维码生成失败: "+str(e)),500

@app.get("/sub/<token>")
def sub(token):
    c=rd(CONF)
    if token!=c.get("sub_token"): return Response("not found",status=404)
    links=[node_link(n) for n in rd(STATE)["nodes"] if n.get("enabled",True)]
    body=base64.b64encode(("\n".join(links)).encode()).decode()
    return Response(body,mimetype="text/plain; charset=utf-8")

@app.get("/api/logs")
def logs():
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    unit=request.args.get("unit","cloudnode-panel")
    if unit not in {"cloudnode-panel",SERVICE,"caddy"}: return jsonify(ok=False,error="invalid unit"),400
    p=subprocess.run(["journalctl","-u",unit,"-n","120","--no-pager"],capture_output=True,text=True)
    return jsonify(ok=True,unit=unit,logs=(p.stdout or p.stderr)[-12000:])

@app.post("/api/backup")
def backup():
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    out=HOME/f"backup-{int(time.time())}.tar.gz"
    with tarfile.open(out,"w:gz") as t:
        for p in [CONF,STATE]:
            if p.exists(): t.add(p,arcname=p.name)
        if XRAY.exists(): t.add(XRAY,arcname="xray-config.json")
    os.chmod(out,0o600)
    return jsonify(ok=True,path=str(out))

@app.post("/api/service/<action>")
def service(action):
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    if action not in {"start","stop","restart"}: return jsonify(ok=False,error="invalid action"),400
    p=subprocess.run(["systemctl",action,SERVICE],capture_output=True,text=True)
    return jsonify(ok=p.returncode==0,error=(p.stderr or p.stdout).strip() if p.returncode else None)

if __name__=="__main__":
    init(); app.run("127.0.0.1",8088)
