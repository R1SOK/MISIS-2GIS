from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from api import app as api_app  # подключаем бэкенд (роуты /routes, /routing, /recordings и т.д.)

app = FastAPI(title="2GIS Wearables – UI")
app.include_router(api_app.router)

# ---------------- UI: список ----------------
@app.get("/ui", response_class=HTMLResponse)
def ui_index():
    return """
<!doctype html><html lang="ru"><head>
  <meta charset="utf-8" />
  <title>Маршруты</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#0b0c0f;color:#e8eaed}
    header{padding:16px 20px;border-bottom:1px solid #222}
    .container{padding:20px;max-width:980px;margin:0 auto}
    .grid{display:grid;grid-template-columns:1fr;gap:12px}
    .card{background:#111418;border:1px solid #222;border-radius:14px;padding:14px}
    a{color:#8ab4f8;text-decoration:none}
    button{background:#1a73e8;color:white;border:0;border-radius:10px;padding:10px 14px;cursor:pointer}
    input{background:#0e1116;color:#e8eaed;border:1px solid #333;border-radius:10px;padding:10px}
    .muted{color:#9aa0a6}
  </style>
</head><body>
<header>
  <div class="container" style="display:flex;justify-content:space-between;gap:12px;align-items:center">
    <div>
      <h2 style="margin:0">2GIS Wearables – Routes</h2>
      <div class="muted">Список сохранённых маршрутов</div>
    </div>
    <div style="display:flex;gap:8px">
      <a href="/ui/record"><button>🔴 Запись</button></a>
      <a href="/ui/create"><button>+ Создать маршрут</button></a>
    </div>
  </div>
</header>

<div class="container">
  <div style="margin-bottom:10px;display:flex;gap:8px;flex-wrap:wrap">
    <input id="q" placeholder="Поиск по имени..." style="flex:1;min-width:180px"/>
    <button id="searchBtn">Искать</button>
  </div>
  <div id="list" class="grid"></div>
</div>

<script>
async function load(q=""){
  const r = await fetch("/routes"+(q?`?q=${encodeURIComponent(q)}`:""));
  const data = await r.json();
  const list = document.getElementById("list");
  list.innerHTML = "";
  if(!data.items || data.items.length===0){
    list.innerHTML = '<div class="card">Маршрутов пока нет. Создай или запиши первый!</div>';
    return;
  }
  for(const it of data.items){
    const div = document.createElement("div");
    div.className="card";
    div.innerHTML = `
      <div style="display:flex;justify-content:space-between;gap:8px;align-items:center">
        <div>
          <div style="font-size:18px;font-weight:600"><a href="/ui/route/${it.id}">${it.name}</a></div>
          <div class="muted">Длина: ${(it.length_m/1000).toFixed(2)} км</div>
          <div class="muted">Теги: ${it.tags.join(", ") || "—"}</div>
        </div>
        <div style="text-align:right">
          <div style="font-variant:all-small-caps">${it.congestion_level}</div>
          <div class="muted">рейтинг: ${it.avg_rating.toFixed(1)} (${it.ratings_count})</div>
        </div>
      </div>`;
    list.appendChild(div);
  }
}
document.getElementById("searchBtn").onclick = ()=>load(document.getElementById("q").value);
load();
</script>
</body></html>
    """

# ---------------- UI: создание + предпросмотр 2ГИС ----------------
@app.get("/ui/create", response_class=HTMLResponse)
def ui_create():
    return """
<!doctype html><html lang="ru"><head>
  <meta charset="utf-8" />
  <title>Создать маршрут</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <script src="https://mapgl.2gis.com/api/js/v1"></script>
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#0b0c0f;color:#e8eaed}
    a{color:#8ab4f8;text-decoration:none}
    header{padding:16px 20px;border-bottom:1px solid #222}
    .container{padding:20px;max-width:1100px;margin:0 auto}
    .card{background:#111418;border:1px solid #222;border-radius:14px;padding:14px}
    #map{height:60vh;border-radius:14px;border:1px solid #222}
    input,select{background:#0e1116;color:#e8eaed;border:1px solid #333;border-radius:10px;padding:10px}
    label{display:block;margin:6px 0 2px}
    .row{display:flex;gap:12px;flex-wrap:wrap}
    .row>div{flex:1;min-width:220px}
    button{background:#1a73e8;color:white;border:0;border-radius:10px;padding:10px 14px;cursor:pointer}
    .secondary{background:#2b2f36}
    .muted{color:#9aa0a6}
    .chip{display:inline-block;padding:3px 8px;border:1px solid #2b2f36;border-radius:999px;margin-right:6px}
    .wplist{list-style:none;padding:0;margin:8px 0 0}
    .wplist li{display:flex;align-items:center;gap:8px;padding:8px;border:1px solid #2b2f36;border-radius:10px;margin-bottom:8px;background:#0e1116}
    .wplist code{background:#0b0c0f;border:1px solid #2b2f36;padding:2px 6px;border-radius:6px}
    .wplist .idx{width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;border-radius:999px;background:#1a73e8}
    .wplist .idx span{font-weight:700}
    .wplist .btns button{background:#2b2f36}
    .tagpill{display:inline-block;margin:4px 6px 0 0;padding:6px 10px;border-radius:999px;border:1px solid #2a2e35;cursor:pointer;user-select:none}
    .tagpill input{margin-right:6px}
  </style>
</head><body>
<header>
  <div class="container">
    <a href="/ui">← Назад</a>
    <h2 style="margin:8px 0 0 0">Создать маршрут</h2>
    <div class="muted">Кликни по карте 2+ раза (точки можно менять местами). «Автор» — затычка для UI.</div>
  </div>
</header>

<div class="container">
  <div class="card" style="margin-bottom:12px">
    <div class="row">
      <div>
        <label for="name">Название</label>
        <input id="name" placeholder="Напр: Утренний круг по набережной" style="width:100%"/>
      </div>
      <div>
        <label for="author">Автор (user_id, опц.)</label>
        <input id="author" type="number" min="1" style="width:100%"/>
      </div>
      <div>
        <label for="transport">Перемещение</label>
        <select id="transport">
          <option value="walking" selected>Пешком</option>
          <option value="bicycle">Велосипед</option>
        </select>
      </div>
    </div>

    <label>Основные теги</label>
    <div id="tagsBox"></div>
    <div class="row" style="margin-top:6px">
      <div>
        <label for="customTags">Свои теги (через запятую)</label>
        <input id="customTags" placeholder="например: вечер, освещённость, лайтово" style="width:100%"/>
      </div>
      <div style="display:flex;align-items:flex-end;gap:8px">
        <button class="secondary" id="clearTagsBtn" type="button">Очистить выбранные</button>
      </div>
    </div>

    <div style="margin-top:8px" class="muted">Выбранные точки: <span id="cnt">0</span></div>
    <ul id="wpList" class="wplist"></ul>
  </div>

  <div id="map"></div>
  <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
    <button class="secondary" id="undoBtn" type="button">↶ Удалить последнюю точку</button>
    <button class="secondary" id="clearBtn" type="button">Очистить</button>
    <div style="flex:1"></div>
    <span class="chip" id="lenChip">Длина: —</span>
    <button id="saveBtn" disabled>Сохранить маршрут</button>
  </div>
</div>

<script>
const API_KEY = "3d318c5f-c356-4aa9-8d32-c4eadc2e4c26";
const map = new mapgl.Map('map', { center:[37.6184,55.7512], zoom: 12, key: API_KEY });

let waypoints = []; // [[lon,lat], ...]
let markers = [];
let routeLine = null;
const cntEl = document.getElementById("cnt");
const lenChip = document.getElementById("lenChip");
const saveBtn = document.getElementById("saveBtn");
const wpList = document.getElementById("wpList");

// теги
const suggestedTags = ["по парку","по набережной","пересеченная местность","плоский","рельефный","короткий","длинный","вечер","утро","зима","лето","освещённость","с коляской"];
function renderTags(){
  const box = document.getElementById("tagsBox");
  box.innerHTML = "";
  suggestedTags.forEach(tag=>{
    const id = "tag__" + tag.replace(/\\s+/g,"_");
    const el = document.createElement("label");
    el.className = "tagpill";
    el.innerHTML = `<input type="checkbox" id="${id}" value="${tag}"> ${tag}`;
    box.appendChild(el);
  });
}
renderTags();
document.getElementById("clearTagsBtn").onclick = ()=>{
  document.querySelectorAll("#tagsBox input[type=checkbox]").forEach(cb=>cb.checked=false);
  document.getElementById("customTags").value = "";
};

function updateCnt(){ cntEl.textContent = String(waypoints.length); }
function renderWpList(){
  wpList.innerHTML = "";
  waypoints.forEach(([lon,lat],i)=>{
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="idx"><span>${i+1}</span></div>
      <code>lat ${Number(lat).toFixed(5)}, lon ${Number(lon).toFixed(5)}</code>
      <div class="btns" style="margin-left:auto;display:flex;gap:6px">
        <button type="button" data-act="up" data-i="${i}">↑</button>
        <button type="button" data-act="down" data-i="${i}">↓</button>
        <button type="button" data-act="remove" data-i="${i}">✕</button>
      </div>`;
    wpList.appendChild(li);
  });
}
function swap(arr, i, j){ const t = arr[i]; arr[i]=arr[j]; arr[j]=t; }
wpList.addEventListener("click", (e)=>{
  const btn = e.target.closest("button"); if(!btn) return;
  const i = Number(btn.getAttribute("data-i"));
  const act = btn.getAttribute("data-act");
  if(act==="remove"){ if(markers[i]) markers[i].destroy(); waypoints.splice(i,1); markers.splice(i,1); }
  else if(act==="up" && i>0){ swap(waypoints,i,i-1); swap(markers,i,i-1); }
  else if(act==="down" && i<waypoints.length-1){ swap(waypoints,i,i+1); swap(markers,i,i+1); }
  updateCnt(); renderWpList(); preview();
});

function renderRoute(coords){
  if(routeLine){ routeLine.destroy(); routeLine=null; }
  if(!coords || !coords.length){ lenChip.textContent="Длина: —"; saveBtn.disabled=true; return; }
  routeLine = new mapgl.Polyline(map, { coordinates: coords, width: 6, color: "#1a73e8" });
  saveBtn.disabled=false;
}
async function preview(){
  if(waypoints.length < 2){ renderRoute([]); return; }
  const transport = document.getElementById("transport").value;
  const body = { transport, waypoints: waypoints.map(([lon,lat])=>({lon,lat})) };
  try{
    const r = await fetch("/routing/preview",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    if(!r.ok){ throw new Error(await r.text()); }
    const data = await r.json();
    renderRoute(data.coordinates);
    lenChip.textContent = "Длина: " + (data.length_m/1000).toFixed(2) + " км";
  }catch(e){ console.error(e); renderRoute([]); lenChip.textContent="Длина: —"; }
}

const mapClick = (ev)=>{
  const [lon,lat] = ev.lngLat;
  waypoints.push([lon,lat]);
  const m = new mapgl.Marker(map,{coordinates:[lon,lat]});
  markers.push(m);
  updateCnt(); renderWpList(); preview();
};
map.on("click", mapClick);

document.getElementById("undoBtn").onclick = ()=>{ waypoints.pop(); const m=markers.pop(); if(m) m.destroy(); updateCnt(); renderWpList(); preview(); };
document.getElementById("clearBtn").onclick = ()=>{ waypoints=[]; markers.forEach(m=>m.destroy()); markers=[]; updateCnt(); renderWpList(); preview(); };
document.getElementById("transport").onchange = preview;

document.getElementById("saveBtn").onclick = async ()=>{
  const name = document.getElementById("name").value.trim();
  const authorRaw = document.getElementById("author").value.trim();
  const author_id = authorRaw? Number(authorRaw) : null;
  const checked = Array.from(document.querySelectorAll("#tagsBox input[type=checkbox]:checked")).map(x=>x.value);
  const customRaw = document.getElementById("customTags").value.trim();
  const customTags = customRaw ? customRaw.split(",").map(s=>s.trim()).filter(Boolean) : [];
  const tags = [...checked, ...customTags];
  if(!name){ alert("Введите название"); return; }
  if(!routeLine){ alert("Постройте маршрут (2+ точки)"); return; }

  // актуальная геометрия
  const transport = document.getElementById("transport").value;
  const pr = await fetch("/routing/preview",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({transport,waypoints:waypoints.map(([lon,lat])=>({lon,lat}))})});
  if(!pr.ok){ alert("Не удалось получить маршрут у 2ГИС"); return; }
  const prev = await pr.json();
  const poly = prev.coordinates.map(([lon,lat])=>({lat,lon}));

  const payload = { name, author_id, tags, points: poly };
  const btn = document.getElementById("saveBtn");
  btn.disabled = true; btn.textContent = "Сохраняю…";
  try{
    const r = await fetch("/routes",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    if(!r.ok){ throw new Error(await r.text()); }
    const data = await r.json();
    window.location.href = "/ui/route/" + data.id;
  }catch(e){ alert("Ошибка: " + (e.message || e)); }
  finally{ btn.disabled=false; btn.textContent="Сохранить маршрут"; }
};

updateCnt(); renderWpList();
</script>
</body></html>
    """

# ---------------- UI: просмотр маршрута ----------------
@app.get("/ui/route/{route_id}", response_class=HTMLResponse)
def ui_route_detail(route_id: int):
    return f"""
<!doctype html><html lang="ru"><head>
  <meta charset="utf-8" />
  <title>Маршрут #{route_id}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <script src="https://mapgl.2gis.com/api/js/v1"></script>
  <style>
    body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#0b0c0f;color:#e8eaed}}
    header{{padding:16px 20px;border-bottom:1px solid #222}}
    .container{{padding:20px;max-width:980px;margin:0 auto}}
    .card{{background:#111418;border:1px solid #222;border-radius:14px;padding:14px}}
    #map{{height:60vh;border-radius:14px;border:1px solid #222}}
    a{{color:#8ab4f8;text-decoration:none}}
    .muted{{color:#9aa0a6}}
  </style>
</head><body>
<header>
  <div class="container">
    <a href="/ui">← Назад</a>
    <h2 style="margin:8px 0 0 0">Маршрут #{route_id}</h2>
  </div>
</header>
<div class="container">
  <div id="info" class="card" style="margin-bottom:12px">Загрузка…</div>
  <div id="map"></div>
</div>

<script>
const API_KEY = "3d318c5f-c356-4aa9-8d32-c4eadc2e4c26";
const map = new mapgl.Map('map', {{ center:[37.6184,55.7512], zoom: 12, key: API_KEY }});

async function main(){{
  const r = await fetch("/routes/{route_id}");
  if(!r.ok){{ document.getElementById("info").innerText="Маршрут не найден"; return; }}
  const data = await r.json();
  document.getElementById("info").innerHTML = `
    <div style="display:flex;justify-content:space-between;gap:8px;align-items:center">
      <div>
        <div style="font-size:18px;font-weight:600">${{data.name}}</div>
        <div class="muted">Длина: ${{(data.length_m/1000).toFixed(2)}} км</div>
        <div class="muted">Теги: ${{data.tags.join(", ") || "—"}}</div>
      </div>
      <div style="text-align:right">
        <div style="font-variant:all-small-caps">${{data.congestion_level}}</div>
        <div class="muted">рейтинг: ${{data.avg_rating.toFixed(1)}} (${{data.ratings_count}})</div>
      </div>
    </div>`;

  const coords = data.points.map(p => [p.lon, p.lat]);
  if(coords.length){{
    new mapgl.Polyline(map, {{ coordinates: coords, width: 6, color: "#1a73e8" }});
    let minx=coords[0][0], maxx=coords[0][0], miny=coords[0][1], maxy=coords[0][1];
    coords.forEach(([x,y])=>{{ if(x<minx)minx=x; if(x>maxx)maxx=x; if(y<miny)miny=y; if(y>maxy)maxy=y; }});
    map.setBounds([[minx,miny],[maxx,maxy]], {{ padding: 40, animate: true }});
  }}
}}
main();
</script>
</body></html>
    """

# ---------------- UI: запись трека (устойчивый вариант) ----------------
@app.get("/ui/record", response_class=HTMLResponse)
def ui_record():
    return """
<!doctype html><html lang="ru"><head>
  <meta charset="utf-8" />
  <title>Запись трека</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <script src="https://mapgl.2gis.com/api/js/v1"></script>
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#0b0c0f;color:#e8eaed}
    header{padding:16px 20px;border-bottom:1px solid #222}
    .container{padding:20px;max-width:980px;margin:0 auto}
    .card{background:#111418;border:1px solid #222;border-radius:14px;padding:14px}
    #map{height:60vh;border-radius:14px;border:1px solid #222}
    input,select{background:#0e1116;color:#e8eaed;border:1px solid #333;border-radius:10px;padding:10px}
    button{background:#1a73e8;color:white;border:0;border-radius:10px;padding:10px 14px;cursor:pointer}
    button.secondary{background:#2b2f36}
    .muted{color:#9aa0a6}
    .row{display:flex;gap:12px;flex-wrap:wrap}
    .row>div{flex:1;min-width:220px}
    .pill{display:inline-block;padding:4px 10px;border:1px solid #2b2f36;border-radius:999px;margin-right:8px}
    .err{color:#ff8a80}
  </style>
</head><body>
<header>
  <div class="container">
    <a href="/ui">← Назад</a>
    <h2 style="margin:8px 0 0 0">Запись трека</h2>
    <div class="muted">Шаги: «Запись» → дождаться первой фиксации → «Стоп» → ввести название → «Сохранить».</div>
  </div>
</header>

<div class="container">
  <div class="card" style="margin-bottom:12px">
    <div class="row">
      <div>
        <label>Перемещение</label>
        <select id="transport">
          <option value="walking" selected>Пешком</option>
          <option value="bicycle">Велосипед</option>
        </select>
      </div>
      <div style="display:flex;align-items:flex-end;gap:8px">
        <button id="startBtn">🔴 Запись</button>
        <button id="pauseBtn" class="secondary" disabled>⏸ Пауза</button>
        <button id="resumeBtn" class="secondary" disabled>▶ Возобновить</button>
        <button id="stopBtn" class="secondary" disabled>■ Стоп</button>
        <button id="testBtn" class="secondary" title="Добавить точку вручную (для отладки)">+ Тест-точка</button>
      </div>
    </div>
    <div style="margin-top:8px">
      <span class="pill">Статус: <b id="status">ожидание</b></span>
      <span class="pill">Точек: <b id="cnt">0</b></span>
      <span class="pill">Длина: <b id="len">0.00 км</b></span>
      <span class="pill">Время: <b id="time">00:00</b></span>
      <span class="pill">Последняя: <b id="last">—</b></span>
    </div>
    <div class="err" id="err"></div>
  </div>

  <div id="map"></div>

  <div class="card" style="margin-top:12px">
    <div class="row">
      <div><input id="name" placeholder="Название трека (обязательно)" style="width:100%"/></div>
      <div><input id="tags" placeholder="Теги (через запятую)" style="width:100%"/></div>
      <div style="display:flex;align-items:flex-end"><button id="saveBtn" disabled>Сохранить маршрут</button></div>
    </div>
  </div>
</div>

<script>
const API_KEY = "3d318c5f-c356-4aa9-8d32-c4eadc2e4c26";
const map = new mapgl.Map('map', { center:[37.6184,55.7512], zoom: 14, key: API_KEY });
let routeLine = null;
let track = []; // [[lon,lat], ...]

// простая длина
function hav(a,b){
  const R=6371000, toRad=x=>x*Math.PI/180;
  const [lon1,lat1]=a, [lon2,lat2]=b;
  const dLat=toRad(lat2-lat1), dLon=toRad(lon2-lon1);
  const s=Math.sin(dLat/2)**2 + Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dLon/2)**2;
  return 2*R*Math.asin(Math.sqrt(s));
}

function renderTrack(){
  if(routeLine){ routeLine.destroy(); routeLine=null; }
  if(track.length < 2) return;
  routeLine = new mapgl.Polyline(map, { coordinates: track, width: 6, color: "#1a73e8" });
  let minx=track[0][0], maxx=track[0][0], miny=track[0][1], maxy=track[0][1];
  track.forEach(([x,y])=>{ if(x<minx)minx=x; if(x>maxx)maxx=x; if(y<miny)miny=y; if(y>maxy)maxy=y; });
  map.setBounds([[minx,miny],[maxx,maxy]], { padding: 40, animate: true });
}
function totalLen(){
  let L=0; for(let i=1;i<track.length;i++) L += hav(track[i-1], track[i]); return L;
}

// UI
const statusEl = document.getElementById("status");
const cntEl = document.getElementById("cnt");
const lenEl = document.getElementById("len");
const timeEl = document.getElementById("time");
const lastEl = document.getElementById("last");
const errEl = document.getElementById("err");
const startBtn = document.getElementById("startBtn");
const pauseBtn = document.getElementById("pauseBtn");
const resumeBtn = document.getElementById("resumeBtn");
const stopBtn = document.getElementById("stopBtn");
const saveBtn = document.getElementById("saveBtn");
const transportSel = document.getElementById("transport");
const testBtn = document.getElementById("testBtn");

let recordingId = null;
let watchId = null;
let startedAt = null;
let timerInt = null;
let paused = false;

function setErr(msg){ errEl.textContent = msg || ""; }
function fmtTime(ms){ const s=Math.floor(ms/1000), m=Math.floor(s/60), ss=s%60; return String(m).padStart(2,"0")+":"+String(ss).padStart(2,"0"); }

async function pollLive(){
  if(!recordingId) return;
  try{
    const r = await fetch(`/recordings/${recordingId}/live`);
    if(!r.ok) return;
    const data = await r.json();
    cntEl.textContent = String(data.points.length);
    lenEl.textContent = (data.length_m/1000).toFixed(2)+" км";
    if(data.points.length){
      const p = data.points[data.points.length-1];
      lastEl.textContent = p.lat.toFixed(5)+", "+p.lon.toFixed(5);
    }
    track = data.points.map(p=>[p.lon,p.lat]);
    renderTrack();
  }catch(_){}
  if(startedAt){ timeEl.textContent = fmtTime(Date.now()-startedAt.getTime()); }
}

function addLocalPoint(lon,lat){
  if(track.length){
    const d = hav(track[track.length-1], [lon,lat]);
    if(d < 5) return; // фильтр шума
  }
  track.push([lon,lat]);
  cntEl.textContent = String(track.length);
  lenEl.textContent = (totalLen()/1000).toFixed(2)+" км";
  lastEl.textContent = lat.toFixed(5)+", "+lon.toFixed(5);
  renderTrack();
}

testBtn.onclick = async ()=>{
  //  добавляет точку рядом с последней — для диагностики канала клиент->сервер
  let lon=37.6184, lat=55.7512;
  if(track.length){ lon = track[track.length-1][0] + (Math.random()-0.5)*0.001; lat = track[track.length-1][1] + (Math.random()-0.5)*0.001; }
  addLocalPoint(lon,lat);
  if(recordingId){
    await fetch(`/recordings/${recordingId}/point`, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ lat, lon })});
  }
};

async function startRecording(){
  setErr("");
  if(!("geolocation" in navigator)){ setErr("Браузер не поддерживает геолокацию"); return; }
  startBtn.disabled = true; pauseBtn.disabled = true; resumeBtn.disabled = true; stopBtn.disabled = true;
  statusEl.textContent = "получаю первую точку…";

  // 1) Прогрев: быстрая первая фиксация (может быть неточная, это нормально)
  const warmupOpts = { enableHighAccuracy: false, maximumAge: 30000, timeout: 60000 };
  try{
    await new Promise((res, rej)=>{
      navigator.geolocation.getCurrentPosition(
        pos => res(pos),
        err => rej(err),
        warmupOpts
      );
    });
  }catch(e){
    // даже если «timeout», всё равно стартуем watch — иногда первая точка прилетит далее
    console.warn("warmup error:", e);
  }

  // 2) Создаём запись на сервере
  const transport = transportSel.value;
  const resp = await fetch("/recordings/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({ transport })});
  if(!resp.ok){ setErr("Не удалось начать запись на сервере"); startBtn.disabled=false; return; }
  const js = await resp.json();
  recordingId = js.recording_id;

  // 3) Запускаем watchPosition с более строгими настройками
  statusEl.textContent = "идёт запись";
  pauseBtn.disabled = false; stopBtn.disabled = false; transportSel.disabled = true;
  startedAt = new Date();
  timerInt = setInterval(pollLive, 2000);

  const watchOpts = { enableHighAccuracy: true, maximumAge: 2000, timeout: 120000 };
  watchId = navigator.geolocation.watchPosition(async (pos)=>{
    if(paused) return;
    const { latitude, longitude, altitude } = pos.coords;
    addLocalPoint(longitude, latitude);
    if(recordingId){
      try{
        await fetch(`/recordings/${recordingId}/point`, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ lat: latitude, lon: longitude, ele: altitude || null })});
      }catch(_){}
    }
  }, (err)=>{
    console.error(err);
    setErr("Геолокация: " + (err.message || err.code || "ошибка"));
  }, watchOpts);
}

startBtn.onclick = startRecording;

pauseBtn.onclick = ()=>{ paused = true; pauseBtn.disabled=true; resumeBtn.disabled=false; statusEl.textContent="пауза"; };
resumeBtn.onclick = ()=>{ paused = false; pauseBtn.disabled=false; resumeBtn.disabled=true; statusEl.textContent="идёт запись"; };

stopBtn.onclick = ()=>{
  if(watchId !== null){ navigator.geolocation.clearWatch(watchId); watchId = null; }
  stopBtn.disabled = true; pauseBtn.disabled = true; resumeBtn.disabled = true;
  if(timerInt){ clearInterval(timerInt); timerInt = null; }
  statusEl.textContent = "остановлено — введите название и сохраните";
  saveBtn.disabled = false;
};

async function saveRoute(){
  const name = document.getElementById("name").value.trim();
  const tagsRaw = document.getElementById("tags").value.trim();
  const tags = tagsRaw ? tagsRaw.split(",").map(s=>s.trim()).filter(Boolean) : [];
  if(!recordingId){ setErr("Нет активной записи"); return; }
  if(!name){ setErr("Введите название"); return; }
  saveBtn.disabled = true; saveBtn.textContent = "Сохраняю…";
  try{
    const r = await fetch(`/recordings/${recordingId}/stop`, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ name, tags })});
    if(!r.ok){ throw new Error(await r.text()); }
    const data = await r.json();
    window.location.href = "/ui/route/" + data.route.id;
  }catch(e){
    setErr("Сохранение не удалось: " + (e.message || e));
    saveBtn.disabled = false; saveBtn.textContent = "Сохранить маршрут";
  }
}
saveBtn.onclick = saveRoute;

// если вкладка скрывается — ставим паузу (экономия батареи)
document.addEventListener("visibilitychange", ()=>{ if(document.hidden) paused = true; });

</script>
</body></html>
    """
