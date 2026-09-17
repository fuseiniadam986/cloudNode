import os,json,secrets,time,uuid,subprocess
from pathlib import Path
from flask import Flask,render_template,request,jsonify,session,redirect
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
        CONF.write_text(json.dumps({"user":"admin","password":generate_password_hash(os.getenv("CLOUDNODE_PASSWORD","change-me-now"))}))
        os.chmod(CONF,0o600)
    if not STATE.exists():
        STATE.write_text('{"nodes":[]}'); os.chmod(STATE,0o600)

def rd(p): init(); return json.loads(p.read_text())
def wr(p,o):
    t=p.with_suffix(".tmp"); t.write_text(json.dumps(o,ensure_ascii=False,indent=2)); os.chmod(t,0o600); t.replace(p)
def auth(): return bool(session.get("ok"))
def running():
    return subprocess.run(["systemctl","is-active",SERVICE],capture_output=True,text=True).stdout.strip()=="active"

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
    return jsonify(ok=True,running=running(),nodes=rd(STATE)["nodes"],version="0.2.0-beta")

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

@app.post("/api/service/<action>")
def service(action):
    if not auth(): return jsonify(ok=False,error="unauthorized"),401
    if action not in {"start","stop","restart"}: return jsonify(ok=False,error="invalid action"),400
    p=subprocess.run(["systemctl",action,SERVICE],capture_output=True,text=True)
    return jsonify(ok=p.returncode==0,error=(p.stderr or p.stdout).strip() if p.returncode else None)

if __name__=="__main__":
    init(); app.run("127.0.0.1",8088)
