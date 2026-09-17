let state={nodes:[]};
async function api(u,o={}){let r=await fetch(u,{headers:{"Content-Type":"application/json"},...o}),d=await r.json();if(!r.ok||d.ok===false)throw Error(d.error||"操作失败");return d}
function esc(s){let d=document.createElement("div");d.textContent=s;return d.innerHTML}
function toast(s){let d=document.createElement("div");d.className="toast";d.textContent=s;toasts.appendChild(d);setTimeout(()=>d.remove(),2500)}
async function loadState(){try{state=await api("/api/state");run.textContent=state.running?"● 服务运行中":"● 服务已停止";num.textContent=state.nodes.length+" 个节点";render()}catch(e){toast(e.message)}}
function render(){let q=search.value.toLowerCase(),a=state.nodes.filter(n=>(n.name+" "+n.host).toLowerCase().includes(q));rows.innerHTML=a.map((n,i)=>`<tr><td>${i+1}</td><td><b>${esc(n.name)}</b></td><td><span class="pill">运行中</span></td><td>${esc(n.host)}</td><td>${n.port}</td><td>${new Date(n.created*1000).toLocaleString()}</td><td><button onclick="copyText('${n.uuid}')">复制 UUID</button> <button class="danger" onclick="removeNode('${n.id}')">删除</button></td></tr>`).join("")||"<tr><td colspan=7>暂无节点</td></tr>"}
function showAdd(){modal.classList.add("show")}function hideAdd(){modal.classList.remove("show")}
async function createNode(){try{await api("/api/nodes",{method:"POST",body:JSON.stringify({name:name.value,host:host.value,port:+port.value})});hideAdd();toast("节点创建成功");loadState()}catch(e){toast(e.message)}}
async function removeNode(id){if(!confirm("确定删除这个节点？"))return;try{await api("/api/nodes/"+id,{method:"DELETE"});toast("已删除");loadState()}catch(e){toast(e.message)}}
async function serviceAction(a){try{await api("/api/service/"+a,{method:"POST"});toast("操作成功");setTimeout(loadState,400)}catch(e){toast(e.message)}}
async function copyText(s){await navigator.clipboard.writeText(s);toast("复制成功")}
loadState();