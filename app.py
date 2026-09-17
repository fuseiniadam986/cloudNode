import os,json,secrets,time,uuid,subprocess,base64,tarfile,io,re
from pathlib import Path
from urllib.parse import quote
from flask import Flask,render_template,request,jsonify,session,redirect,Response,abort
from werkzeug.security import generate_password_hash,check_password_hash

HOME=Path(os.getenv("CLOUDNODE_HOME","/etc/cloudnode-panel"))
STATE=HOME/"state.json"; CONF=HOME/"panel.json"
XRAY=Path(os.getenv("XRAY_CONFIG","/usr/local/etc/xray/config.json"))
SERVICE=os.getenv("XRAY_SERVICE","xray")
API_PORT=int(os.getenv("XRAY_API_PORT","10085"))
VERSION="0.4.0-beta"
HELPER=os.getenv("CLOUDNODE_HELPER","/usr/local/sbin/cloudnode-root-helper")
app=Flask(__name__)
app.secret_key=os.getenv("CLOUDNODE_SECRET",secrets.token_hex(32))
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Strict")
LOGIN_FAILS={}
SAFE_PROTOCOLS={"vless-xhttp","vless-ws","vless-reality","trojan-tcp"}

def csrf_token():
    if "csrf" not in session:
        session["csrf"]=secrets.token_urlsafe(32)
    return session["csrf"]
def require_csrf():
    if request.method in {"POST","PUT","DELETE"} and request.headers.get("X-CSRF-Token")!=session.get("csrf"):
        abort(403)
@app.before_request
def guard_mutations():
    if request.endpoint!="login":
        require_csrf()

def init():
    HOME.mkdir(parents=True,exist_ok=True)
    if not CONF.exists():
        pwd=os.getenv("CLOUDNODE_PASSWORD")
        if not pwd:
            raise RuntimeError("CLOUDNODE_PASSWORD 未设置，请通过 install.sh 安装或配置环境变量")
        CONF.write_text(json.dumps({"user":"admin","password":generate_password_hash(pwd),"sub_token":secrets.token_urlsafe(24)}))
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
def helper(*args):
    cmd=["sudo","-n",HELPER,*args] if os.geteuid()!=0 else [HELPER,*args]
    return subprocess.run(cmd,capture_output=True,text=True)
def x25519():
    p=subprocess.run(["xray","x25519"],capture_output=True,text=True)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout).strip())
    priv=re.search(r"Private key:\s*([A-Za-z0-9_-]+)",p.stdout)
    pub=re.search(r"Public key:\s*([A-Za-z0-9_-]+)",p.stdout)
    if not priv or not pub: raise RuntimeError("无法生成 REALITY 密钥")
    return priv.group(1),pub.group(1)
def normalize_node(n):
    n.setdefault("protocol","vless-xhttp")
    n.setdefault("enabled",True)
    n.setdefault("path","/"+secrets.token_urlsafe(9))
    n.setdefault("uuid",str(uuid.uuid4()))
    n.setdefault("password",secrets.token_urlsafe(16))
    n.setdefault("sni",n.get("host",""))
    n.setdefault("reality_dest","www.microsoft.com:443")
    n.setdefault("short_id",secrets.token_hex(4))
    if n["protocol"]=="vless-reality" and not n.get("private_key"):
        n["private_key"],n["public_key"]=x25519()
    return n
def public_node(n):
    return {k:n.get(k) for k in ["id","name","host","port","protocol","enabled","created","sni","reality_dest"]}
def node_link(n):
    n=normalize_node(n)
    tag=quote(n["name"])
    if n["protocol"]=="vless-ws":
        params=f"encryption=none&type=ws&path={quote(n['path'])}&security=none"
        return f"vless://{n['uuid']}@{n['host']}:{n['port']}?{params}#{tag}"
    if n["protocol"]=="vless-reality":
        params=f"encryption=none&type=tcp&security=reality&sni={quote(n['sni'])}&fp=chrome&pbk={quote(n.get('public_key',''))}&sid={quote(n['short_id'])}&flow=xtls-rprx-vision"
        return f"vless://{n['uuid']}@{n['host']}:{n['port']}?{params}#{tag}"
    if n["protocol"]=="trojan-tcp":
        params="security=none&type=tcp"
        return f"trojan://{quote(n['password'])}@{n['host']}:{n['port']}?{params}#{tag}"
    params=f"encryption=none&type=xhttp&path={quote(n['path'])}&security=none"
    return f"vless://{n['uuid']}@{n['host']}:{n['port']}?{params}#{tag}"
def find_node(st,nid):
    return next((n for n in st["nodes"] if n["id"]==nid),None)

def build(nodes):
    ins=[]
    for n in nodes:
        n=normalize_node(n)
        if n.get("enabled",True):
            tag="cloudnode-"+n["id"]
            if n["protocol"]=="trojan-tcp":
                ins.append({"tag":tag,"listen":"0.0.0.0","port":n["port"],"protocol":"trojan",
                    "settings":{"clients":[{"password":n["password"],"email":n["name"]}]},
                    "streamSettings":{"network":"tcp","security":"none"}})
            else:
                client={"id":n["uuid"],"email":n["name"]}
                if n["protocol"]=="vless-reality": client["flow"]="xtls-rprx-vision"
                stream={"network":"xhttp","security":"none","xhttpSettings":{"path":n["path"],"mode":"auto"}}
                if n["protocol"]=="vless-ws":
                    stream={"network":"ws","security":"none","wsSettings":{"path":n["path"]}}
                if n["protocol"]=="vless-reality":
                    stream={"network":"tcp","security":"reality","realitySettings":{"show":False,"dest":n["reality_dest"],"xver":0,
                        "serverNames":[n["sni"]],"privateKey":n["private_key"],"shortIds":[n["short_id"]]}}
                ins.append({"tag":tag,"listen":"0.0.0.0","port":n["port"],"protocol":"vless",
                    "settings":{"clients":[client],"decryption":"none"},"streamSettings":stream})
    ins.append({"tag":"api","listen":"127.0.0.1","port":API_PORT,"protocol":"dokodemo-door","settings":{"address":"127.0.0.1"}})
    return {"log":{"loglevel":"warning"},"stats":{},"api":{"tag":"api","services":["StatsService"]},
            "policy":{"levels":{"0":{"statsUserUplink":True,"statsUserDownlink":True}}},
            "inbounds":ins,
            "outbounds":[{"protocol":"freedom","tag":"direct"},{"protocol":"blackhole","tag":"blocked"},{"protocol":"freedom","tag":"api"}],
            "routing":{"rules":[{"type":"field","inboundTag":["api"],"outboundTag":"api"}]}}

def apply_config():
    cfg=build(rd(STATE)["nodes"])
    gen=HOME/"generated"; gen.mkdir(parents=True,exist_ok=True)
    tmp=gen/"xray.json"
    tmp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2))
    os.chmod(tmp,0o600)
    p=helper("apply-xray",str(tmp))
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout).strip())

@app.route("/login",methods=["GET","POST"])
def login():
    init(); err=""
    if request.method=="POST":
        if request.form.get("csrf")!=session.get("csrf"):
            abort(403)
        ip=request.headers.get("X-Forwarded-For",request.remote_addr or "").split(",")[0].strip()
        fails=[t for t in LOGIN_FAILS.get(ip,[]) if time.time()-t<300]
        if len(fails)>=8:
            return render_template("login.html",err="尝试次数过多，请稍后再试",csrf=csrf_token()),429
        c=rd(CONF)
        if request.form.get("user")==c["user"] and check_password_hash(c["password"],request.form.get("password","")):
            session.clear(); session["ok"]=True; csrf_token(); LOGIN_FAILS.pop(ip,None); return redirect("/")
        fails.append(time.time()); LOGIN_FAILS[ip]=fails
        err="用户名或密码错误"
    return render_template("login.html",err=err,csrf=csrf_token())

@app.get("/logout")
def logout(): session.clear(); return redirect("/login")

@app.get("/")
def home(): return render_template("index.html") if auth() else redirect("/login")

@app.get("/api/state")
def state():
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    c=rd(CONF)
    st=rd(STATE); changed=False
    for n in st["nodes"]:
        before=json.dumps(n,sort_keys=True); normalize_node(n); changed=changed or before!=json.dumps(n,sort_keys=True)
    if changed: wr(STATE,st)
    return jsonify(ok=True,running=running(),nodes=[public_node(n) for n in st["nodes"]],version=VERSION,csrf=csrf_token(),
                   sub_url="/sub/"+c["sub_token"],bbr=bbr_status(),caddy=unit_active("caddy"))

@app.post("/api/nodes")
def create():
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    d=request.get_json(force=True)
    name=str(d.get("name","")).strip(); host=str(d.get("host","")).strip()
    protocol=str(d.get("protocol","vless-xhttp")).strip()
    try: port=int(d.get("port",443))
    except ValueError: return jsonify(ok=False,error="端口格式错误"),400
    if not name or not host or not 1<=port<=65535:
        return jsonify(ok=False,error="请检查名称、域名/IP和端口"),400
    st=rd(STATE)
    if any(n["port"]==port for n in st["nodes"]):
        return jsonify(ok=False,error="该端口已被 CloudNode 节点使用"),409
    if protocol not in SAFE_PROTOCOLS:
        return jsonify(ok=False,error="协议类型不支持"),400
    n={"id":secrets.token_hex(4),"name":name[:32],"host":host[:253],"port":port,"protocol":protocol,
       "uuid":str(uuid.uuid4()),"path":"/"+secrets.token_urlsafe(9),
       "enabled":True,"created":int(time.time()),"sni":str(d.get("sni",host)).strip() or host,
       "reality_dest":str(d.get("reality_dest","www.microsoft.com:443")).strip() or "www.microsoft.com:443",
       "short_id":secrets.token_hex(4),"password":secrets.token_urlsafe(16)}
    normalize_node(n)
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
    protocol=str(d.get("protocol",n.get("protocol","vless-xhttp"))).strip()
    if not name or not host or not 1<=port<=65535:
        return jsonify(ok=False,error="请检查名称、域名/IP和端口"),400
    if any(x["id"]!=nid and x["port"]==port for x in st["nodes"]):
        return jsonify(ok=False,error="该端口已被 CloudNode 节点使用"),409
    if protocol not in SAFE_PROTOCOLS:
        return jsonify(ok=False,error="协议类型不支持"),400
    n.update({"name":name[:32],"host":host[:253],"port":port,"enabled":enabled,"protocol":protocol,
              "sni":str(d.get("sni",n.get("sni",host))).strip() or host,
              "reality_dest":str(d.get("reality_dest",n.get("reality_dest","www.microsoft.com:443"))).strip() or "www.microsoft.com:443"})
    normalize_node(n)
    wr(STATE,st)
    try: apply_config()
    except Exception as e:
        wr(STATE,old); return jsonify(ok=False,error=str(e)),500
    return jsonify(ok=True,node=n)

@app.post("/api/nodes/<nid>/refresh")
def refresh_node(nid):
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    st=rd(STATE); old=json.loads(json.dumps(st)); n=find_node(st,nid)
    if not n: return jsonify(ok=False,error="节点不存在"),404
    n["uuid"]=str(uuid.uuid4()); n["path"]="/"+secrets.token_urlsafe(9); n["password"]=secrets.token_urlsafe(16); n["short_id"]=secrets.token_hex(4)
    if n.get("protocol")=="vless-reality": n["private_key"],n["public_key"]=x25519()
    wr(STATE,st)
    try: apply_config()
    except Exception as e:
        wr(STATE,old); return jsonify(ok=False,error=str(e)),500
    return jsonify(ok=True,node=n,link=node_link(n))

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

@app.get("/api/traffic")
def traffic():
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    rows=[]
    for n in rd(STATE)["nodes"]:
        up=down=0
        for kind in [("uplink","up"),("downlink","down")]:
            p=subprocess.run(["xray","api","statsquery","--server",f"127.0.0.1:{API_PORT}","-name",f"user>>>{n['name']}>>>traffic>>>{kind[0]}"],capture_output=True,text=True)
            m=re.search(r"value:\s*(\d+)",p.stdout)
            if kind[1]=="up": up=int(m.group(1)) if m else 0
            else: down=int(m.group(1)) if m else 0
        rows.append({"id":n["id"],"name":n["name"],"up":up,"down":down})
    return jsonify(ok=True,traffic=rows)

@app.post("/api/system/optimize")
def optimize():
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    p=helper("optimize-bbr")
    if p.returncode: return jsonify(ok=False,error=(p.stderr or p.stdout).strip()),500
    return jsonify(ok=True,bbr=bbr_status())

@app.post("/api/service/<action>")
def service(action):
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    if action not in {"start","stop","restart"}: return jsonify(ok=False,error="invalid action"),400
    p=helper("service-xray",action)
    return jsonify(ok=p.returncode==0,error=(p.stderr or p.stdout).strip() if p.returncode else None)

if __name__=="__main__":
    init(); app.run("127.0.0.1",8088)
