from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from api import app as api_app  # импортируем бэкенд, чтобы он жил в одном процессе

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
    <div><a href="/ui/create"><button>+ Создать маршрут</button></a></div>
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
    list.innerHTML = '<div class="card">Маршрутов пока нет. Создай первый!</div>';
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

# ---------------- UI: создание + предпросмотр по 2ГИС ----------------
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
    .flex{display:flex;gap:12px;flex-wrap:wrap}
    .col{flex:1;min-width:320px}
    /* список точек */
    .wplist{list-style:none;padding:0;margin:8px 0 0}
    .wplist li{display:flex;align-items:center;gap:8px;padding:8px;border:1px solid #2b2f36;border-radius:10px;margin-bottom:8px;background:#0e1116}
    .wplist code{background:#0b0c0f;border:1px solid #2b2f36;padding:2px 6px;border-radius:6px}
    .wplist .idx{width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;border-radius:999px;background:#1a73e8}
    .wplist .idx span{font-weight:700}
    .wplist .btns button{background:#2b2f36}
    /* теги */
    .tagpill{display:inline-block;margin:4px 6px 0 0;padding:6px 10px;border-radius:999px;border:1px solid #2a2e35;cursor:pointer;user-select:none}
    .tagpill input{margin-right:6px}
  </style>
</head><body>
<header>
  <div class="container">
    <a href="/ui">← Назад</a>
    <h2 style="margin:8px 0 0 0">Создать маршрут</h2>
    <div class="muted">Кликни по карте 2+ раза (можно 3+ точек). Точки можно менять местами.</div>
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

    <div style="margin-top:8px" class="muted">
      Выбранные точки: <span id="cnt">0</span>
    </div>
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
const API_KEY = "3d318c5f-c356-4aa9-8d32-c4eadc2e4c26"; // только для карты (MapGL). Для маршрутов используем backend.

const map = new mapgl.Map('map', {
  center: [37.6184, 55.7512],
  zoom: 12,
  key: API_KEY
});

let waypoints = []; // [[lon,lat], ...]
let markers = [];
let routeLine = null;
const cntEl = document.getElementById("cnt");
const lenChip = document.getElementById("lenChip");
const saveBtn = document.getElementById("saveBtn");
const wpList = document.getElementById("wpList");

// -------- теги: преднабор + очистка --------
const suggestedTags = [
  "по парку","по набережной","пересеченная местность","плоский","рельефный",
  "короткий","длинный","вечер","утро","зима","лето","освещённость","с коляской"
];
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

// -------- список точек (перестановка) --------
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
  if(act==="remove"){
    if(markers[i]) markers[i].destroy();
    waypoints.splice(i,1); markers.splice(i,1);
  }else if(act==="up" && i>0){
    swap(waypoints, i, i-1); swap(markers, i, i-1);
  }else if(act==="down" && i<waypoints.length-1){
    swap(waypoints, i, i+1); swap(markers, i, i+1);
  }else return;
  updateCnt(); renderWpList(); preview();
});

// -------- рисование и превью маршрута через бэкенд --------
function renderRoute(coords){
  if(routeLine){ routeLine.destroy(); routeLine = null; }
  if(!coords || !coords.length){ lenChip.textContent = "Длина: —"; saveBtn.disabled = true; return; }
  routeLine = new mapgl.Polyline(map, { coordinates: coords, width: 6, color: "#1a73e8" });
  saveBtn.disabled = false;
}
async function preview(){
  if(waypoints.length < 2){ renderRoute([]); return; }
  const transport = document.getElementById("transport").value;
  const body = { transport, waypoints: waypoints.map(([lon,lat]) => ({ lon, lat })) };
  try{
    const r = await fetch("/routing/preview", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
    });
    if(!r.ok){ const t = await r.text(); throw new Error(t); }
    const data = await r.json();
    renderRoute(data.coordinates);
    lenChip.textContent = "Длина: " + (data.length_m/1000).toFixed(2) + " км";
  }catch(e){
    console.error(e);
    renderRoute([]); lenChip.textContent = "Длина: —";
  }
}

// -------- карта / кнопки --------
const mapClick = (ev) => {
  const [lon, lat] = ev.lngLat;
  waypoints.push([lon, lat]);
  const m = new mapgl.Marker(map, { coordinates: [lon, lat] });
  markers.push(m);
  updateCnt(); renderWpList(); preview();
};
map.on("click", mapClick);

document.getElementById("undoBtn").onclick = ()=>{
  waypoints.pop();
  const m = markers.pop(); if(m) m.destroy();
  updateCnt(); renderWpList(); preview();
};
document.getElementById("clearBtn").onclick = ()=>{
  waypoints = [];
  markers.forEach(m => m.destroy()); markers = [];
  updateCnt(); renderWpList(); preview();
};
document.getElementById("transport").onchange = preview;

// -------- сохранение --------
document.getElementById("saveBtn").onclick = async ()=>{
  const name = document.getElementById("name").value.trim();
  const authorRaw = document.getElementById("author").value.trim();
  const author_id = authorRaw? Number(authorRaw) : null;

  const checked = Array.from(document.querySelectorAll("#tagsBox input[type=checkbox]:checked")).map(x=>x.value);
  const customRaw = document.getElementById("customTags").value.trim();
  const customTags = customRaw ? customRaw.split(",").map(s=>s.trim()).filter(Boolean) : [];
  const tags = [...checked, ...customTags];

  if(!name){ alert("Введите название"); return; }
  if(!routeLine){ alert("Постройте маршрут (2+ клика по карте)"); return; }

  // берём актуальную геометрию от бэкенда
  const transport = document.getElementById("transport").value;
  const pr = await fetch("/routing/preview",{method:"POST",headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ transport, waypoints: waypoints.map(([lon,lat])=>({lon,lat})) })
  });
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
  }catch(e){
    alert("Ошибка: " + (e.message || e));
  }finally{
    btn.disabled = false; btn.textContent = "Сохранить маршрут";
  }
};

// стартовое состояние
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
  const line = new mapgl.Polyline(map, {{ coordinates: coords, width: 6, color: "#1a73e8" }});
  let minx=coords[0][0], maxx=coords[0][0], miny=coords[0][1], maxy=coords[0][1];
  coords.forEach(([x,y])=>{{ if(x<minx)minx=x; if(x>maxx)maxx=x; if(y<miny)miny=y; if(y>maxy)maxy=y; }});
  map.setBounds([ [minx,miny], [maxx,maxy] ], {{ animate: true, padding: 32 }});
}}
main();
</script>
</body></html>
    """
