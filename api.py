from __future__ import annotations

import os
import json
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Literal, Tuple, Dict

import httpx
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, conlist, conint
from sqlalchemy import create_engine, func, select, ForeignKey
from sqlalchemy.orm import declarative_base, Mapped, mapped_column, relationship, sessionmaker, Session

# =========================
# Config
# =========================
DGIS_API_KEY = os.getenv("DGIS_API_KEY", "3d318c5f-c356-4aa9-8d32-c4eadc2e4c26").strip()
ROUTING_URL = "https://routing.api.2gis.com/routing/7.0.0/global"

# =========================
# DB setup (SQLite)
# =========================
engine = create_engine("sqlite:///./routes.db", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()

class Route(Base):
    __tablename__ = "routes"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(index=True)
    author_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    geometry_json: Mapped[str] = mapped_column()  # JSON array of points [{lat,lon,ele?,ts?}]
    length_m: Mapped[float] = mapped_column(default=0.0)
    elev_up_m: Mapped[float] = mapped_column(default=0.0)
    elev_down_m: Mapped[float] = mapped_column(default=0.0)
    tags_json: Mapped[str] = mapped_column(default="[]")
    avg_rating: Mapped[float] = mapped_column(default=0.0)
    ratings_count: Mapped[int] = mapped_column(default=0)

    ratings: Mapped[List["RouteRating"]] = relationship(back_populates="route", cascade="all, delete-orphan")
    activities: Mapped[List["Activity"]] = relationship(back_populates="route", cascade="all, delete-orphan")

class RouteRating(Base):
    __tablename__ = "route_ratings"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    stars: Mapped[int]
    comment: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    route: Mapped[Route] = relationship(back_populates="ratings")

class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    ended_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    route: Mapped[Route] = relationship(back_populates="activities")

Base.metadata.create_all(engine)

# =========================
# Schemas
# =========================
class Point(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    ele: Optional[float] = None
    ts: Optional[datetime] = None

class RouteCreate(BaseModel):
    name: str
    author_id: Optional[int] = None
    points: conlist(Point, min_length=2)
    tags: Optional[List[str]] = None

class RoutePublic(BaseModel):
    id: int
    name: str
    author_id: Optional[int]
    created_at: datetime
    points: List[Point]
    length_m: float
    elev_up_m: float
    elev_down_m: float
    tags: List[str]
    avg_rating: float
    ratings_count: int
    congestion_level: Literal["low", "medium", "high"]
    congestion_score: float

class RoutesList(BaseModel):
    items: List[RoutePublic]
    total: int

class TagsPatch(BaseModel):
    add: Optional[List[str]] = None
    set: Optional[List[str]] = None

class RatingCreate(BaseModel):
    stars: conint(ge=1, le=5)
    comment: Optional[str] = None
    user_id: Optional[int] = None

class ActivityCreate(BaseModel):
    route_id: int
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

class WeatherAdvice(BaseModel):
    route_id: int
    at: datetime
    advice: str
    severity: Literal["none", "low", "medium", "high"]

# ===== /routing/preview (pairwise) =====
class PreviewPoint(BaseModel):
    lat: float
    lon: float

class PreviewRequest(BaseModel):
    transport: Literal["walking", "bicycle"] = "walking"
    waypoints: conlist(PreviewPoint, min_length=2)

class PreviewResponse(BaseModel):
    coordinates: List[List[float]]  # [[lon,lat], ...] for MapGL polyline
    length_m: float

# ===== Recording schemas =====
class RecordingStartReq(BaseModel):
    author_id: Optional[int] = None

class RecordingStartResp(BaseModel):
    recording_id: str
    started_at: datetime

class RecordingPointReq(BaseModel):
    lat: float
    lon: float
    ele: Optional[float] = None
    ts: Optional[datetime] = None

class RecordingLiveResp(BaseModel):
    id: str
    started_at: datetime
    points: List[Point]
    length_m: float

class RecordingStopReq(BaseModel):
    name: str
    author_id: Optional[int] = None
    tags: Optional[List[str]] = None

class RecordingStopResp(BaseModel):
    route: RoutePublic

# =========================
# Utils
# =========================
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

EARTH_R = 6371000.0

def haversine_m(lat1, lon1, lat2, lon2) -> float:
    from math import radians, sin, cos, asin, sqrt
    if lat1 == lat2 and lon1 == lon2:
        return 0.0
    rlat1, rlon1, rlat2, rlon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = sin(dlat/2)**2 + cos(rlat1)*cos(rlat2)*sin(dlon/2)**2
    c = 2*asin(sqrt(a))
    return EARTH_R * c

def compute_length(points: List[Point]) -> float:
    dist = 0.0
    for i in range(1, len(points)):
        p1, p2 = points[i-1], points[i]
        dist += haversine_m(p1.lat, p1.lon, p2.lat, p2.lon)
    return dist

def compute_elevation(points: List[Point]) -> Tuple[float, float]:
    up = down = 0.0
    prev = None
    for p in points:
        if p.ele is None:
            prev = None
            continue
        if prev is not None:
            d = p.ele - prev
            if d > 0: up += d
            else: down += -d
        prev = p.ele
    return round(up, 1), round(down, 1)

def normalize_tags(raw: Optional[List[str]]) -> List[str]:
    tags = set()
    if raw:
        for t in raw:
            t = (t or "").strip().lower()
            if t:
                tags.add(t)
    return sorted(tags)

def keyword_autotags(name: str, points: List[Point]) -> List[str]:
    name_l = name.lower()
    out = set()
    if any(k in name_l for k in ["парк", "park"]): out.add("по парку")
    if any(k in name_l for k in ["набережн", "embankment", "river", "река"]): out.add("по набережной")
    if any(k in name_l for k in ["лес", "trail", "пересеч"]): out.add("пересеченная местность")
    L = compute_length(points)
    if L < 3000: out.add("короткий")
    elif L > 10000: out.add("длинный")
    return sorted(out)

def congestion_from_activities(db: Session, route_id: int, window_minutes: int = 120) -> Tuple[str, float]:
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    count = db.scalar(select(func.count(Activity.id)).where(Activity.route_id == route_id, Activity.started_at >= since)) or 0
    score = min(1.0, count/10.0)
    if count <= 2: level = "low"
    elif count <= 6: level = "medium"
    else: level = "high"
    return level, score

def points_to_json(points: List[Point]) -> str:
    # В pydantic v2 JSON-совместимые типы даёт mode="json" (datetime -> ISO строка)
    return json.dumps([p.model_dump(mode="json") for p in points], ensure_ascii=False)

def json_to_points(js: str) -> List[Point]:
    # Поддержка старых записей с ISO-строкой в ts
    arr = json.loads(js)
    out: List[Point] = []
    for p in arr:
        ts = p.get("ts")
        if isinstance(ts, str):
            try:
                p["ts"] = datetime.fromisoformat(ts)
            except Exception:
                p["ts"] = None
        out.append(Point(**p))
    return out

def weather_stub(route: Route, at: Optional[datetime]) -> WeatherAdvice:
    pts = json_to_points(route.geometry_json)
    mid = pts[len(pts)//2]
    at = at or datetime.now(timezone.utc)
    key = f"{round(mid.lat,4)}:{round(mid.lon,4)}:{at.replace(minute=0, second=0, microsecond=0).isoformat()}"
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16) % 100
    if h < 20:
        return WeatherAdvice(route_id=route.id, at=at, advice="Возможен дождь через ~30–60 мин, порывы ветра 8–10 м/с.", severity="high")
    elif h < 50:
        return WeatherAdvice(route_id=route.id, at=at, advice="Облачно, возможны порывы ветра.", severity="medium")
    elif h < 80:
        return WeatherAdvice(route_id=route.id, at=at, advice="Слабая облачность, без осадков 2 часа.", severity="low")
    else:
        return WeatherAdvice(route_id=route.id, at=at, advice="Погодных предупреждений нет.", severity="none")

# =========================
# FastAPI app
# =========================
app = FastAPI(title="2GIS Wearables – Routes MVP", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

@app.get("/health")
def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}

# =========================
# 2GIS Routing helpers (оставляем — используется в /routing/preview)
# =========================
def _parse_linestring(sel: Optional[str]) -> List[List[float]]:
    if not sel or "LINESTRING" not in sel:
        return []
    inner = sel.replace("LINESTRING(", "").rstrip(")")
    out: List[List[float]] = []
    for pair in inner.split(","):
        parts = pair.strip().split()
        if len(parts) >= 2:
            out.append([float(parts[0]), float(parts[1])])
    return out

async def _request_pair_route(
    client: httpx.AsyncClient,
    a: PreviewPoint,
    b: PreviewPoint,
    transport: str,
    api_key: str
) -> List[List[float]]:
    async def do_req(tr: str) -> List[List[float]]:
        body = {
            "points": [
                {"type": "stop", "lon": a.lon, "lat": a.lat},
                {"type": "stop", "lon": b.lon, "lat": b.lat},
            ],
            "transport": tr,
            "locale": "ru",
            "output": "detailed",
        }
        url = f"{ROUTING_URL}?key={api_key}"
        resp = await client.post(url, json=body)
        if resp.status_code != 200:
            return []
        data = resp.json()
        routes = data.get("result") or []
        if not routes:
            return []
        r0 = routes[0]
        coords: List[List[float]] = []

        begin_sel = (((r0.get("begin_pedestrian_path") or {}).get("geometry") or {}).get("selection"))
        coords += _parse_linestring(begin_sel)

        for m in r0.get("maneuvers") or []:
            for g in ((m.get("outcoming_path") or {}).get("geometry") or []):
                coords += _parse_linestring(g.get("selection"))

        end_sel = (((r0.get("end_pedestrian_path") or {}).get("geometry") or {}).get("selection"))
        coords += _parse_linestring(end_sel)
        return coords

    coords = await do_req(transport)
    if not coords and transport == "bicycle":
        coords = await do_req("walking")
    return coords

# =========================
# /routing/preview (склейка сегментов 2+)
# =========================
@app.post("/routing/preview", response_model=PreviewResponse)
async def routing_preview(payload: PreviewRequest):
    if len(payload.waypoints) < 2:
        raise HTTPException(400, "Нужно минимум 2 точки")
    if payload.transport not in ("walking", "bicycle"):
        raise HTTPException(400, "Разрешены только walking/bicycle")

    merged: List[List[float]] = []
    any_success = False

    async with httpx.AsyncClient(timeout=20.0) as client:
        for i in range(len(payload.waypoints) - 1):
            a = payload.waypoints[i]
            b = payload.waypoints[i + 1]
            segment = await _request_pair_route(client, a, b, payload.transport, DGIS_API_KEY)

            if not segment or len(segment) < 2:
                segment = [[a.lon, a.lat], [b.lon, b.lat]]
            else:
                any_success = True

            if not merged:
                merged.extend(segment)
            else:
                if merged[-1] == segment[0]:
                    merged.extend(segment[1:])
                else:
                    merged.extend(segment)

    if not any_success and len(payload.waypoints) >= 2 and not merged:
        merged = [[payload.waypoints[0].lon, payload.waypoints[0].lat],
                  [payload.waypoints[-1].lon, payload.waypoints[-1].lat]]

    poly_pts = [Point(lat=lat, lon=lon) for lon, lat in merged]
    length_m = compute_length(poly_pts)

    return PreviewResponse(coordinates=merged, length_m=round(length_m, 1))

# =========================
# In-memory Recording store (простая заглушка для сессий записи)
# =========================
class _Rec:
    def __init__(self, rec_id: str, author_id: Optional[int]):
        self.id = rec_id
        self.author_id = author_id
        self.started_at = datetime.now(timezone.utc)
        self.points: List[Point] = []

_RECORDINGS: Dict[str, _Rec] = {}

# ===== Recording endpoints =====
@app.post("/recordings/start", response_model=RecordingStartResp)
def rec_start(payload: RecordingStartReq):
    rec_id = uuid.uuid4().hex
    _RECORDINGS[rec_id] = _Rec(rec_id, payload.author_id)
    return RecordingStartResp(recording_id=rec_id, started_at=_RECORDINGS[rec_id].started_at)

@app.post("/recordings/{rec_id}/point")
def rec_point(rec_id: str, payload: RecordingPointReq):
    rec = _RECORDINGS.get(rec_id)
    if not rec:
        raise HTTPException(404, "Recording not found")
    p = Point(lat=payload.lat, lon=payload.lon, ele=payload.ele, ts=payload.ts or datetime.now(timezone.utc))
    rec.points.append(p)
    return {"ok": True, "count": len(rec.points)}

@app.get("/recordings/{rec_id}/live", response_model=RecordingLiveResp)
def rec_live(rec_id: str):
    rec = _RECORDINGS.get(rec_id)
    if not rec:
        raise HTTPException(404, "Recording not found")
    length_m = compute_length(rec.points)
    return RecordingLiveResp(id=rec.id, started_at=rec.started_at, points=rec.points, length_m=round(length_m, 1))

@app.post("/recordings/{rec_id}/stop", response_model=RecordingStopResp)
def rec_stop(rec_id: str, payload: RecordingStopReq, db: Session = Depends(get_db)):
    rec = _RECORDINGS.get(rec_id)
    if not rec:
        raise HTTPException(404, "Recording not found")
    if len(rec.points) < 2:
        raise HTTPException(400, "Недостаточно точек для маршрута")

    points = rec.points
    length_m = compute_length(points)
    up, down = compute_elevation(points)

    tags = set(normalize_tags(payload.tags))
    tags |= set(keyword_autotags(payload.name, points))

    route = Route(
        name=payload.name,
        author_id=payload.author_id if payload.author_id is not None else rec.author_id,
        geometry_json=points_to_json(points),
        length_m=round(length_m, 1),
        elev_up_m=up,
        elev_down_m=down,
        tags_json=json.dumps(sorted(tags), ensure_ascii=False),
    )
    db.add(route); db.commit(); db.refresh(route)

    level, score = congestion_from_activities(db, route.id)

    # очистим сессию записи
    _RECORDINGS.pop(rec_id, None)

    rp = RoutePublic(
        id=route.id, name=route.name, author_id=route.author_id, created_at=route.created_at,
        points=points, length_m=route.length_m, elev_up_m=route.elev_up_m, elev_down_m=route.elev_down_m,
        tags=json.loads(route.tags_json), avg_rating=route.avg_rating, ratings_count=route.ratings_count,
        congestion_level=level, congestion_score=score
    )
    return RecordingStopResp(route=rp)

# =========================
# CRUD: routes, ratings, activities
# =========================
@app.post("/routes", response_model=RoutePublic, summary="Создать маршрут")
def create_route(payload: RouteCreate, db: Session = Depends(get_db)):
    points = payload.points
    length_m = compute_length(points)
    up, down = compute_elevation(points)

    tags = set(normalize_tags(payload.tags))
    tags |= set(keyword_autotags(payload.name, points))

    route = Route(
        name=payload.name,
        author_id=payload.author_id,
        geometry_json=points_to_json(points),
        length_m=round(length_m, 1),
        elev_up_m=up,
        elev_down_m=down,
        tags_json=json.dumps(sorted(tags), ensure_ascii=False),
    )
    db.add(route); db.commit(); db.refresh(route)

    level, score = congestion_from_activities(db, route.id)
    return RoutePublic(
        id=route.id, name=route.name, author_id=route.author_id, created_at=route.created_at,
        points=points, length_m=route.length_m, elev_up_m=route.elev_up_m, elev_down_m=route.elev_down_m,
        tags=json.loads(route.tags_json), avg_rating=route.avg_rating, ratings_count=route.ratings_count,
        congestion_level=level, congestion_score=score
    )

@app.get("/routes", response_model=RoutesList, summary="Список маршрутов")
def list_routes(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, description="поиск по имени"),
    limit: int = 50,
    offset: int = 0
):
    stmt = select(Route).order_by(Route.created_at.desc())
    if q:
        stmt = stmt.where(Route.name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items: List[RoutePublic] = []
    for r in db.scalars(stmt.limit(limit).offset(offset)):
        level, score = congestion_from_activities(db, r.id)
        items.append(RoutePublic(
            id=r.id, name=r.name, author_id=r.author_id, created_at=r.created_at,
            points=json_to_points(r.geometry_json), length_m=r.length_m,
            elev_up_m=r.elev_up_m, elev_down_m=r.elev_down_m,
            tags=json.loads(r.tags_json), avg_rating=r.avg_rating, ratings_count=r.ratings_count,
            congestion_level=level, congestion_score=score
        ))
    return RoutesList(items=items, total=total)

@app.get("/routes/{route_id}", response_model=RoutePublic, summary="Получить маршрут")
def get_route(route_id: int, db: Session = Depends(get_db)):
    r = db.get(Route, route_id)
    if not r:
        raise HTTPException(404, "Route not found")
    level, score = congestion_from_activities(db, r.id)
    return RoutePublic(
        id=r.id, name=r.name, author_id=r.author_id, created_at=r.created_at,
        points=json_to_points(r.geometry_json), length_m=r.length_m,
        elev_up_m=r.elev_up_m, elev_down_m=r.elev_down_m,
        tags=json.loads(r.tags_json), avg_rating=r.avg_rating, ratings_count=r.ratings_count,
        congestion_level=level, congestion_score=score
    )

@app.patch("/routes/{route_id}/tags", response_model=RoutePublic, summary="Обновить теги маршрута")
def patch_tags(route_id: int, payload: TagsPatch, db: Session = Depends(get_db)):
    r = db.get(Route, route_id)
    if not r:
        raise HTTPException(404, "Route not found")
    current = set(json.loads(r.tags_json))
    if payload.set is not None:
        current = set(normalize_tags(payload.set))
    if payload.add:
        current |= set(normalize_tags(payload.add))
    r.tags_json = json.dumps(sorted(current), ensure_ascii=False)
    db.add(r); db.commit(); db.refresh(r)
    level, score = congestion_from_activities(db, r.id)
    return RoutePublic(
        id=r.id, name=r.name, author_id=r.author_id, created_at=r.created_at,
        points=json_to_points(r.geometry_json), length_m=r.length_m,
        elev_up_m=r.elev_up_m, elev_down_m=r.elev_down_m,
        tags=json.loads(r.tags_json), avg_rating=r.avg_rating, ratings_count=r.ratings_count,
        congestion_level=level, congestion_score=score
    )

@app.post("/routes/{route_id}/rate", summary="Оценить маршрут")
def rate_route(route_id: int, payload: RatingCreate, db: Session = Depends(get_db)):
    r = db.get(Route, route_id)
    if not r:
        raise HTTPException(404, "Route not found")
    rating = RouteRating(route_id=route_id, stars=int(payload.stars), comment=payload.comment, user_id=payload.user_id)
    db.add(rating); db.flush()
    avg, cnt = db.execute(select(func.avg(RouteRating.stars), func.count(RouteRating.id)).where(RouteRating.route_id == route_id)).one()
    r.avg_rating = float(avg or 0.0); r.ratings_count = int(cnt or 0)
    db.add(r); db.commit()
    return {"ok": True, "route_id": route_id, "avg_rating": r.avg_rating, "ratings_count": r.ratings_count}

@app.post("/activities", summary="Залогировать активность (для загруженности)")
def create_activity(payload: ActivityCreate, db: Session = Depends(get_db)):
    r = db.get(Route, payload.route_id)
    if not r:
        raise HTTPException(404, "Route not found")
    act = Activity(route_id=payload.route_id, started_at=payload.started_at or datetime.now(timezone.utc), ended_at=payload.ended_at)
    db.add(act); db.commit(); db.refresh(act)
    return {"ok": True, "activity_id": act.id}

@app.get("/routes/{route_id}/congestion")
def route_congestion(route_id: int, window_minutes: int = 120, db: Session = Depends(get_db)):
    r = db.get(Route, route_id)
    if not r:
        raise HTTPException(404, "Route not found")
    level, score = congestion_from_activities(db, route_id, window_minutes)
    return {"route_id": route_id, "window_minutes": window_minutes, "level": level, "score": score}

@app.get("/routes/{route_id}/weather", response_model=WeatherAdvice, summary="Заглушка прогноза погоды")
def route_weather(route_id: int, at: Optional[datetime] = None, db: Session = Depends(get_db)):
    r = db.get(Route, route_id)
    if not r:
        raise HTTPException(404, "Route not found")
    return weather_stub(r, at)
