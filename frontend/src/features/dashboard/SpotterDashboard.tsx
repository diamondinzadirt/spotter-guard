import { useState } from 'react';
import { Activity, ArrowRight, BarChart3, CloudRain, Gauge, Menu, Navigation, Radio, Route, Send, ShieldCheck, Snowflake, Truck, Wind } from 'lucide-react';
import type { Checkpoint, RiskLevel, RouteOption, RoutePlanRequest, RoutePlanResponse, WeatherMetric } from '@/types';
import { planRoutes } from '@/services/mockApi';
import MapCanvas from './MapCanvas';

const riskMeta: Record<RiskLevel, { label: string; color: string; bg: string }> = {
  low: { label: 'Low', color: '#1c8a5b', bg: '#e5f5ed' },
  moderate: { label: 'Moderate', color: '#be8b06', bg: '#fff6d9' },
  high: { label: 'High', color: '#e56f12', bg: '#fff0e2' },
  severe: { label: 'Severe', color: '#d4482e', bg: '#ffebe7' },
  no_travel: { label: 'No travel', color: '#151918', bg: '#e8eae8' },
};

const formatTime = (iso: string) => new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' }).format(new Date(iso));
const formatDuration = (minutes: number) => `${Math.floor(minutes / 60)}h ${minutes % 60}m`;

function Brand() {
  return <div className="brand"><div className="brand-mark"><Truck size={19} strokeWidth={2.6} /></div><div><strong>spotter<span> guard</span></strong><small>WEATHER-AWARE ROUTING</small></div></div>;
}

function RiskBadge({ risk, compact = false }: { risk: RiskLevel; compact?: boolean }) {
  const meta = riskMeta[risk];
  return <span className={`risk-badge ${compact ? 'compact' : ''}`} style={{ color: meta.color, backgroundColor: meta.bg, borderColor: `${meta.color}40` }}><i style={{ backgroundColor: meta.color }} />{meta.label}</span>;
}

function Planner({ request, setRequest, onAnalyze, loading }: { request: RoutePlanRequest; setRequest: (request: RoutePlanRequest) => void; onAnalyze: () => void; loading: boolean }) {
  return <section className="planner panel">
    <div className="panel-title"><div><span className="eyebrow">01 / trip setup</span><h2>Route planner</h2></div><Truck size={19} /></div>
    <label>Origin<input value={request.origin} onChange={(event) => setRequest({ ...request, origin: event.target.value })} /></label>
    <label>Destination<input value={request.destination} onChange={(event) => setRequest({ ...request, destination: event.target.value })} /></label>
    <label>Departure date / time<input type="datetime-local" value={request.departure_time.slice(0, 16)} onChange={(event) => setRequest({ ...request, departure_time: event.target.value })} /></label>
    <label>Load weight <span className="unit">LB</span><input type="number" min="0" value={request.load_weight_lb} onChange={(event) => setRequest({ ...request, load_weight_lb: Number(event.target.value) })} /></label>
    <div className="field-label">Checkpoint interval <span className="unit">MILES</span></div>
    <div className="segmented">{([10, 25, 50] as const).map((value) => <button key={value} className={request.checkpoint_interval_miles === value ? 'active' : ''} onClick={() => setRequest({ ...request, checkpoint_interval_miles: value })}>{value} <span>mi</span></button>)}</div>
    <button className="primary-button" onClick={onAnalyze} disabled={loading}><Send size={16} />{loading ? 'Analyzing corridor…' : 'Analyze routes'}<ArrowRight size={16} /></button>
    <div className="planner-note"><ShieldCheck size={16} /><span>Risk uses driver arrival weather and the assessment load rules.</span></div>
  </section>;
}

function RouteCard({ route, selected, onSelect }: { route: RouteOption; selected: boolean; onSelect: () => void }) {
  return <button className={`route-card ${selected ? 'selected' : ''}`} onClick={onSelect}>
    <div className="route-card-top"><div><div className="route-name">{route.name}{route.recommended && <span className="recommended"><ShieldCheck size={11} /> Recommended</span>}</div><p>{route.description}</p></div><RiskBadge risk={route.overall_risk} compact /></div>
    <div className="route-stats"><div><span>Distance</span><strong>{route.distance_miles} <em>mi</em></strong></div><div><span>Duration</span><strong>{formatDuration(route.duration_minutes)}</strong></div><div><span>Arrival</span><strong>{formatTime(route.arrival_time)}</strong></div></div>
    <div className="route-footer"><span>Severe <b className="danger-text">{route.severe_miles} mi</b></span><span>High <b className="high-text">{route.high_miles} mi</b></span><span>No travel <b>{(route.no_travel_miles ?? 0).toFixed(1)} mi</b></span><span>Avg risk <b>{route.average_risk.toFixed(2)}</b></span></div>
  </button>;
}

function WeatherPanel({ metric, setMetric, slider, setSlider, response }: { metric: WeatherMetric; setMetric: (metric: WeatherMetric) => void; slider: number; setSlider: (value: number) => void; response: RoutePlanResponse }) {
  const icons = { wind: Wind, rain: CloudRain, snow: Snowflake };
  const Icon = icons[metric];
  const frame = response.weather_frames[metric][slider] ?? response.weather_frames[metric][0];
  if (!frame) return <div className="weather-panel panel-content"><p className="weather-note">No forecast frames are available for this response.</p></div>;
  return <div className="weather-panel panel-content"><div className="metric-switcher">{(['wind', 'rain', 'snow'] as WeatherMetric[]).map((item) => { const MetricIcon = icons[item]; return <button key={item} className={metric === item ? 'active' : ''} onClick={() => setMetric(item)}><MetricIcon size={15} />{item}</button>; })}<button><Activity size={15} /></button></div><div className="forecast-card"><div className="forecast-heading"><span className="eyebrow">Forecast / 0–48 h</span><b>+{frame.offset_hours} h</b></div><input type="range" min="0" max="6" value={slider} onChange={(event) => setSlider(Number(event.target.value))} /><div className="forecast-times"><span>Now</span><span>+24h</span><span>+48h</span></div><p>Valid {new Date(frame.valid_at).toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric' })}</p></div><div className="intensity-card"><div className="intensity-title"><Icon size={15} /><span>{metric} intensity</span><b>{metric === 'wind' ? 'mph' : 'in/hr'}</b></div><div className={`gradient-bar ${metric}`} /><div className="intensity-labels"><span>Calm</span><span>Intense</span></div></div><p className="weather-note">The corridor overlay shows modeled {metric} intensity at each forecast hour. Weather intensity is separate from the calculated travel-risk classification.</p></div>;
}

function CheckpointTable({ route, selectedCheckpoint, onCheckpoint }: { route: RouteOption; selectedCheckpoint?: Checkpoint; onCheckpoint: (checkpoint: Checkpoint) => void }) {
  return <div className="checkpoint-table"><div className="table-head"><span>mile</span><span>arrival</span><span>wind</span><span>rain</span><span>snow</span><span>risk</span></div>{route.checkpoints.map((checkpoint) => <button className={selectedCheckpoint?.id === checkpoint.id ? 'active' : ''} key={checkpoint.id} onClick={() => onCheckpoint(checkpoint)}><strong>{checkpoint.mile}</strong><span>{formatTime(checkpoint.arrival_time)}</span><span>{checkpoint.wind_mph}</span><span>{checkpoint.rainfall_in_hr.toFixed(2)}</span><span>{checkpoint.snowfall_in_hr.toFixed(2)}</span><i style={{ backgroundColor: riskMeta[checkpoint.risk_level].color }} /></button>)}</div>;
}

function App() {
  const [request, setRequest] = useState<RoutePlanRequest>({ origin: 'Denver, CO', destination: 'Kansas City, MO', departure_time: '2026-10-19T14:00', load_weight_lb: 42000, checkpoint_interval_miles: 25 });
  const [response, setResponse] = useState<RoutePlanResponse | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState('i70-central');
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<Checkpoint>();
  const [metric, setMetric] = useState<WeatherMetric>('wind');
  const [slider, setSlider] = useState(0);
  const [tab, setTab] = useState<'routes' | 'weather' | 'checkpoints'>('routes');
  const [mobileView, setMobileView] = useState<'map' | 'routes' | 'weather' | 'plan'>('map');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();

  const analyze = async () => { setLoading(true); setError(undefined); try { const next = await planRoutes(request); setResponse(next); setSelectedRouteId(next.recommended_route_id); setSelectedCheckpoint(undefined); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'Unable to analyze this corridor.'); } finally { setLoading(false); } };
  const data = response ?? null;
  const routes = data?.routes ?? [];
  const selectedRoute = routes.find((route) => route.id === selectedRouteId) ?? routes[0];
  const displayRoutes = routes.length ? routes : [];

  return <div className="app-shell">
    <header className="topbar"><Brand /><div className="trip-summary"><b>{request.origin.split(',')[0]}</b><ArrowRight size={13} /><b>{request.destination.split(',')[0]}</b><span className="summary-divider" />{selectedRoute && <><span>{selectedRoute.distance_miles.toFixed(0)} mi</span><span>{formatDuration(selectedRoute.duration_minutes)}</span><span>ETA {formatTime(selectedRoute.arrival_time)}</span></>}</div><div className="header-actions"><RiskBadge risk={selectedRoute?.overall_risk ?? 'low'} compact /><span className="demo-pill"><Radio size={13} /> {data?.data_source === 'live' ? 'Live forecast' : 'Simulated demo'} <span>{data?.safe_route_available === false ? 'No safe route' : 'Backend connected'}</span></span></div><button className="mobile-menu"><Menu size={20} /></button></header>
    <div className="mobile-context"><span className="eyebrow">{mobileView === 'map' ? 'active corridor' : mobileView}</span><strong>{request.origin} <ArrowRight size={13} /> {request.destination}</strong></div>
    <main className="workspace">
      <aside className={`left-column ${mobileView === 'plan' ? 'mobile-visible' : ''}`}><Planner request={request} setRequest={setRequest} onAnalyze={analyze} loading={loading} />{error && <div className="error-state" role="alert">{error}</div>}</aside>
      <section className={`map-column ${mobileView === 'map' ? 'mobile-visible' : ''}`}><MapCanvas routes={displayRoutes} selectedRoute={selectedRoute} frame={data?.weather_frames[metric]?.[slider]} selectedCheckpoint={selectedCheckpoint} onCheckpoint={setSelectedCheckpoint} /></section>
      <aside className={`right-column ${mobileView === 'routes' || mobileView === 'weather' ? 'mobile-visible' : ''}`}>{data?.safe_route_available === false && <div className="unsafe-banner" role="status">No route is safe under the current forecast. Review no-travel segments before dispatch.</div>}<div className="right-tabs">{([['routes', Route], ['weather', BarChart3], ['checkpoints', Gauge]] as const).map(([key, TabIcon]) => <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}><TabIcon size={14} />{key}</button>)}</div>{tab === 'routes' && <div className="routes-list">{routes.length ? routes.map((route) => <RouteCard key={route.id} route={route} selected={route.id === selectedRoute?.id} onSelect={() => { setSelectedRouteId(route.id); setSelectedCheckpoint(undefined); }} />) : <div className="empty-state"><Route size={22} /><strong>Your corridor is ready to analyze</strong><span>Choose your trip inputs, then compare three weather-aware routes.</span></div>}</div>}{tab === 'weather' && data && <WeatherPanel metric={metric} setMetric={setMetric} slider={slider} setSlider={setSlider} response={data} />}{tab === 'checkpoints' && selectedRoute && <CheckpointTable route={selectedRoute} selectedCheckpoint={selectedCheckpoint} onCheckpoint={setSelectedCheckpoint} />}</aside>
    </main>
    <nav className="bottom-nav">{([['map', Navigation], ['routes', Route], ['weather', CloudRain], ['plan', Truck]] as const).map(([key, NavIcon]) => <button key={key} className={mobileView === key ? 'active' : ''} onClick={() => { setMobileView(key); if (key === 'routes') setTab('routes'); if (key === 'weather') setTab('weather'); }}><NavIcon size={18} /><span>{key}</span></button>)}</nav>
  </div>;
}

export default App;
