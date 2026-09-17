let state={nodes:[]},editing=null;
async function api(u,o={}){let r=await fetch(u,{headers:{"Content-Type":"application/json"},...o}),d=await r.json();if(!r.ok||d.ok===false)throw Error(d.error||"操作失败");return d}
function esc(s){let d=document.createElement("div");d.textContent=s;return d.innerHTML}
function toast(s){let d=document.createElement("div");d.className="toast";d.textContent=s;toasts.appendChild(d);setTimeout(()=>d.remove(),2500)}
async function loadState(){try{state=await api("/api/state");run.textContent=state.running?"● Xray 运行中":"● Xray 已停止";num.textContent=state.nodes.length+" 个节点";bbr.textContent="BBR: "+(state.bbr||"-");tls.textContent="HTTPS: "+(state.caddy?"已配置":"未配置");ver.textContent="v"+state.version;render()}catch(e){toast(e.message)}}
function render(){let q=search.value.toLowerCase(),a=state.nodes.filter(n=>(n.name+" "+n.host).toLowerCase().includes(q));rows.innerHTML=a.map((n,i)=>`<tr><td>${i+1}</td><td><b>${esc(n.name)}</b></td><td><span class="pill ${n.enabled===false?"off":""}">${n.enabled===false?"已停用":"运行中"}</span></td><td>${esc(n.host)}</td><td>${n.port}</td><td>${new Date(n.created*1000).toLocaleString()}</td><td><button onclick="showShare('${n.id}')">链接</button> <button onclick="showEdit('${n.id}')">编辑</button> <button onclick="copyText('${n.uuid}')">UUID</button> <button class="danger" onclick="removeNode('${n.id}')">删除</button></td></tr>`).join("")||"<tr><td colspan=7>暂无节点</td></tr>"}
function showAdd(){editing=null;modalTitle.textContent="添加节点";name.value="";host.value="";port.value=443;enabled.value="1";modal.classList.add("show")}
function showEdit(id){let n=state.nodes.find(x=>x.id===id);if(!n)return;editing=id;modalTitle.textContent="编辑节点";name.value=n.name;host.value=n.host;port.value=n.port;enabled.value=n.enabled===false?"0":"1";modal.classList.add("show")}
function hideNodeModal(){modal.classList.remove("show")}
async function saveNode(){try{let body=JSON.stringify({name:name.value,host:host.value,port:+port.value,enabled:enabled.value==="1"});if(editing)await api("/api/nodes/"+editing,{method:"PUT",body});else await api("/api/nodes",{method:"POST",body});hideNodeModal();toast(editing?"节点已更新":"节点创建成功");loadState()}catch(e){toast(e.message)}}
async function removeNode(id){if(!confirm("确定删除这个节点？"))return;try{await api("/api/nodes/"+id,{method:"DELETE"});toast("已删除");loadState()}catch(e){toast(e.message)}}
async function serviceAction(a){try{await api("/api/service/"+a,{method:"POST"});toast("操作成功");setTimeout(loadState,400)}catch(e){toast(e.message)}}
async function copyText(s){await navigator.clipboard.writeText(s);toast("复制成功")}
async function showShare(id){try{let d=await api("/api/nodes/"+id+"/link");shareText.value=d.link;qrImg.src="/api/nodes/"+id+"/qr?t="+Date.now();shareModal.classList.add("show")}catch(e){toast(e.message)}}
function showSub(){subText.value=location.origin+state.sub_url;subModal.classList.add("show")}
async function showLogs(unit="cloudnode-panel"){try{let d=await api("/api/logs?unit="+encodeURIComponent(unit));logText.textContent=d.logs||"暂无日志";logModal.classList.add("show")}catch(e){toast(e.message)}}
async function backupNow(){try{let d=await api("/api/backup",{method:"POST"});toast("备份已创建: "+d.path)}catch(e){toast(e.message)}}
loadState();
