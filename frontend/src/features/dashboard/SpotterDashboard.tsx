import { useCallback, useEffect, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { Activity, ArrowRight, BarChart3, CloudRain, Gauge, LoaderCircle, Navigation, Radio, Route, Send, ShieldCheck, Snowflake, Truck, Wind } from 'lucide-react';
import type { Checkpoint, RiskLevel, RouteOption, RoutePlanRequest, RoutePlanResponse, WeatherMetric } from '@/types';
import { planRoutes } from '@/services/mockApi';
import MapCanvas from './MapCanvas';
import { US_STATES } from '@/data/states';
import { CITIES_BY_STATE } from '@/data/cities';
import { riskBackgrounds, riskColors, riskLabels } from '@/styles/riskColors';

const riskMeta: Record<RiskLevel, { label: string; color: string; bg: string }> = Object.fromEntries(Object.keys(riskColors).map((risk) => [risk, { label: riskLabels[risk as RiskLevel], color: riskColors[risk as RiskLevel], bg: riskBackgrounds[risk as RiskLevel] }])) as Record<RiskLevel, { label: string; color: string; bg: string }>;

const formatTime = (iso: string) => new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' }).format(new Date(iso));
const formatDuration = (minutes: number) => `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
const toLocalDateTimeValue = (date: Date) => { const pad = (value: number) => String(value).padStart(2, '0'); return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`; };
const splitLocation = (value: string) => { const match = value.match(/^(.+),\s*([A-Z]{2})$/i); return { city: match?.[1] ?? value, state: match?.[2]?.toUpperCase() ?? '' }; };
const weatherSeverity = (metric: WeatherMetric, value: number) => {
  const thresholds = metric === 'wind' ? [25, 35, 45, 55] : metric === 'rain' ? [0.1, 0.25, 0.5, 1] : [0.5, 1, 2, 3];
  if (value >= thresholds[3]) return 'No Travel';
  if (value >= thresholds[2]) return 'Severe';
  if (value >= thresholds[1]) return 'High';
  if (value >= thresholds[0]) return 'Moderate';
  return 'Low';
};

function Brand() {
  return <div className="brand"><div className="brand-mark"><img src="/images/spotter-logo.png" alt="Spotter Guard logo" /></div><div><strong>spotter<span> guard</span></strong><small>WEATHER-AWARE ROUTING</small></div></div>;
}

function RiskBadge({ risk, compact = false }: { risk: RiskLevel; compact?: boolean }) {
  const meta = riskMeta[risk];
  return <span className={`risk-badge ${compact ? 'compact' : ''}`} style={{ color: meta.color, backgroundColor: meta.bg, borderColor: `${meta.color}40` }}><i style={{ backgroundColor: meta.color }} />{meta.label}</span>;
}

function Planner({ request, setRequest, onAnalyze, loading }: { request: RoutePlanRequest; setRequest: (request: RoutePlanRequest) => void; onAnalyze: () => void; loading: boolean }) {
  const initialOrigin = splitLocation(request.origin); const initialDestination = splitLocation(request.destination);
  const [originState, setOriginState] = useState(initialOrigin.state); const [originCity, setOriginCity] = useState(initialOrigin.city);
  const [destinationState, setDestinationState] = useState(initialDestination.state); const [destinationCity, setDestinationCity] = useState(initialDestination.city);
  const updateLocation = (field: 'origin' | 'destination', city: string, state: string) => setRequest({ ...request, [field]: city && state ? `${city}, ${state}` : '' });
  const originCities = CITIES_BY_STATE[originState] ?? []; const destinationCities = CITIES_BY_STATE[destinationState] ?? [];
  return <section className="planner panel">
    <div className="panel-title"><div><h2>Enter Your Trip Details</h2><p className="planner-helper">Choose your route, departure time and load weight.</p></div><Truck size={19} /></div>
    <div className="location-fields"><div><label>Starting State<select value={originState} onChange={(event) => { const state = event.target.value; setOriginState(state); setOriginCity(''); updateLocation('origin', '', state); }}><option value="">Select state</option>{US_STATES.map(([code, name]) => <option key={code} value={code}>{name} ({code})</option>)}</select></label><label>Starting City<select value={originCity} disabled={!originState} onChange={(event) => { const city = event.target.value; setOriginCity(city); updateLocation('origin', city, originState); }}><option value="">Select city</option>{originCities.map((city) => <option key={city} value={city}>{city}</option>)}</select></label></div><div><label>Destination State<select value={destinationState} onChange={(event) => { const state = event.target.value; setDestinationState(state); setDestinationCity(''); updateLocation('destination', '', state); }}><option value="">Select state</option>{US_STATES.map(([code, name]) => <option key={code} value={code}>{name} ({code})</option>)}</select></label><label>Destination City<select value={destinationCity} disabled={!destinationState} onChange={(event) => { const city = event.target.value; setDestinationCity(city); updateLocation('destination', city, destinationState); }}><option value="">Select city</option>{destinationCities.map((city) => <option key={city} value={city}>{city}</option>)}</select></label></div></div>
    <label>Departure date / time<input type="datetime-local" min={toLocalDateTimeValue(new Date())} value={request.departure_time.slice(0, 16)} onChange={(event) => setRequest({ ...request, departure_time: event.target.value })} /></label>
    <label>Load weight <span className="unit">LB</span><input type="number" min="0" value={request.load_weight_lb} onChange={(event) => setRequest({ ...request, load_weight_lb: Number(event.target.value) })} /></label>
    <div className="field-label">Checkpoint interval <span className="unit">MILES</span></div>
    <div className="segmented">{([10, 25, 50] as const).map((value) => <button key={value} className={request.checkpoint_interval_miles === value ? 'active' : ''} onClick={() => setRequest({ ...request, checkpoint_interval_miles: value })}>{value} <span>mi</span></button>)}</div>
    <button className="primary-button" onClick={onAnalyze} disabled={loading} aria-busy={loading}>{loading ? <LoaderCircle className="loading-spinner" size={16} aria-hidden="true" /> : <Send size={16} />}{loading ? 'Analyzing routes…' : 'Analyze routes'}<ArrowRight size={16} /></button>
    <div className="planner-note"><ShieldCheck size={16} /><span>Risk uses driver arrival weather and the assessment load rules.</span></div>
  </section>;
}

function RouteCard({ route, selected, onSelect }: { route: RouteOption; selected: boolean; onSelect: () => void }) {
  return <button className={`route-card ${selected ? 'selected' : ''}`} onClick={onSelect}>
    <div className="route-card-top"><div><div className="route-name">{route.name}{route.recommended && <span className="recommended"><ShieldCheck size={11} /> Recommended</span>}</div><p>{route.description.toLowerCase().includes('fixture') || route.description.toLowerCase().includes('offline') ? 'Weather-aware truck route alternative.' : route.description}</p></div><RiskBadge risk={route.overall_risk} compact /></div>
    <div className="route-stats"><div><span>Distance</span><strong>{route.distance_miles.toFixed(1)} <em>mi</em></strong></div><div><span>Duration</span><strong>{formatDuration(route.duration_minutes)}</strong></div><div><span>Arrival</span><strong>{formatTime(route.arrival_time)}</strong></div></div>
    <div className="route-footer"><span>Severe <b className="danger-text">{route.severe_miles} mi</b></span><span>High <b className="high-text">{route.high_miles} mi</b></span><span>No travel <b>{(route.no_travel_miles ?? 0).toFixed(1)} mi</b></span><span>Avg risk <b>{route.average_risk.toFixed(2)}</b></span></div>
  </button>;
}

function WeatherPanel({ metric, setMetric, slider, setSlider, response, routeId }: { metric: WeatherMetric; setMetric: (metric: WeatherMetric) => void; slider: number; setSlider: (value: number) => void; response: RoutePlanResponse; routeId?: string }) {
  const icons = { wind: Wind, rain: CloudRain, snow: Snowflake };
  const Icon = icons[metric];
  const routeFrames = routeId ? response.weather_frames_by_route?.[routeId] : undefined;
  const frames = routeFrames?.[metric] ?? response.weather_frames[metric];
  const frame = frames[slider] ?? frames[0];
  if (!frame) return <div className="weather-panel panel-content"><p className="weather-note">No forecast frames are available for this response.</p></div>;
  const values = frame.points.map((point) => point.value ?? point.intensity * (metric === 'wind' ? 60 : metric === 'rain' ? 1 : 3));
  const peak = Math.max(...values, 0);
  const average = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
  const maxScale = metric === 'wind' ? 60 : metric === 'rain' ? 1 : 3;
  const unit = metric === 'wind' ? 'mph' : 'in/hr';
  const peakPosition = Math.min(100, (peak / maxScale) * 100);
  const averagePosition = Math.min(100, (average / maxScale) * 100);
  const metricLabel = metric[0].toUpperCase() + metric.slice(1);
  const peakSeverity = weatherSeverity(metric, peak);
  const averageSeverity = weatherSeverity(metric, average);
  const measurement = (value: number) => `${value.toFixed(metric === 'wind' ? 0 : 2)} ${unit}`;
  return <div className="weather-panel panel-content"><div className="metric-switcher">{(['wind', 'rain', 'snow'] as WeatherMetric[]).map((item) => { const MetricIcon = icons[item]; return <button key={item} className={metric === item ? 'active' : ''} onClick={() => setMetric(item)}><MetricIcon size={15} />{item}</button>; })}<button><Activity size={15} /></button></div><div className="forecast-card"><div className="forecast-heading"><span className="eyebrow">Forecast / 0–48 h</span><b>+{frame.offset_hours} h</b></div><input type="range" min="0" max="6" value={slider} onChange={(event) => setSlider(Number(event.target.value))} /><div className="forecast-times"><span>Now</span><span>+24h</span><span>+48h</span></div><p>Valid {new Date(frame.valid_at).toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric' })}</p></div><div className="intensity-card"><div className="intensity-title"><Icon size={15} /><span>{metric} intensity</span><b>{unit}</b></div><div className="intensity-scale" aria-label={`${metric} intensity scale from calm to no travel`}><div className="intensity-scale-bar" /><button type="button" className="intensity-marker peak" style={{ left: `${peakPosition}%` }} aria-label={`Peak ${metricLabel}, ${measurement(peak)}, ${peakSeverity}. Strongest ${metric} detected along the route.`}><span className="marker-tooltip"><strong>Peak {metricLabel} · {measurement(peak)}</strong><em>{peakSeverity} — Strongest {metric} detected along the route.</em></span></button><button type="button" className="intensity-marker average" style={{ left: `${averagePosition}%` }} aria-label={`Average ${metricLabel}, ${measurement(average)}, ${averageSeverity}. Typical ${metric} across the route.`}><span className="marker-tooltip"><strong>Average {metricLabel} · {measurement(average)}</strong><em>{averageSeverity} — Typical {metric} across the route.</em></span></button></div><div className="intensity-labels"><span>Calm</span><span>Moderate</span><span>High</span><span>Severe</span><span>No travel</span></div><div className="intensity-reading"><span><i className="marker-key peak-key" />Peak <b>{measurement(peak)}</b></span><span><i className="marker-key average-key" />Average <b>{measurement(average)}</b></span></div></div><p className="weather-note">Simulated forecast intensity at mapped points. This weather-only scale is separate from final load-adjusted route risk.</p></div>;
}

function CheckpointTable({ route, selectedCheckpoint, onCheckpoint }: { route: RouteOption; selectedCheckpoint?: Checkpoint; onCheckpoint: (checkpoint: Checkpoint) => void }) {
  return <div className="checkpoint-table"><div className="table-head"><span>mile</span><span>arrival</span><span>wind<br /><em>mph</em></span><span>rain<br /><em>in/hr</em></span><span>snow<br /><em>in/hr</em></span><span>risk</span></div>{route.checkpoints.map((checkpoint) => <button className={selectedCheckpoint?.id === checkpoint.id ? 'active' : ''} key={checkpoint.id} onClick={() => onCheckpoint(checkpoint)}><strong className="checkpoint-mile">{checkpoint.mile.toFixed(1)}</strong><span className="checkpoint-arrival">{formatTime(checkpoint.arrival_time)}</span><span className="checkpoint-wind">{Math.round(checkpoint.wind_mph)}</span><span className="checkpoint-rain">{checkpoint.rainfall_in_hr.toFixed(2)}</span><span className="checkpoint-snow">{checkpoint.snowfall_in_hr.toFixed(2)}</span><i title={`Risk: ${riskMeta[checkpoint.risk_level].label}`} aria-label={`Risk: ${riskMeta[checkpoint.risk_level].label}`} style={{ backgroundColor: riskMeta[checkpoint.risk_level].color }} /></button>)}</div>;
}

export function App() {
  const [request, setRequest] = useState<RoutePlanRequest>(() => { const departure = new Date(Date.now() + 60 * 60 * 1000); return { origin: 'Denver, CO', destination: 'Kansas City, MO', departure_time: toLocalDateTimeValue(departure), load_weight_lb: 42000, checkpoint_interval_miles: 25 }; });
  const [response, setResponse] = useState<RoutePlanResponse | null>(null);
  const [selectedRouteId, setSelectedRouteId] = useState('i70-central');
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<Checkpoint>();
  const [metric, setMetric] = useState<WeatherMetric>('wind');
  const [slider, setSlider] = useState(0);
  const [tab, setTab] = useState<'routes' | 'weather' | 'checkpoints'>('routes');
  const [mobileView, setMobileView] = useState<'map' | 'routes' | 'weather' | 'plan'>('map');
  const [sheetSnap, setSheetSnap] = useState<'collapsed' | 'half' | 'expanded'>('half');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [errorToast, setErrorToast] = useState<string>();
  const [updateMessage, setUpdateMessage] = useState<string>();
  const updateMessageTimer = useRef<ReturnType<typeof setTimeout>>();
  const requestSequence = useRef(0);
  const abortController = useRef<AbortController>();
  const sheetDrag = useRef<{ startY: number; startSnap: 'collapsed' | 'half' | 'expanded' }>();

  const analyze = async () => { const departure = new Date(request.departure_time); const now = new Date(); now.setSeconds(0, 0); const origin = request.origin.trim(); const destination = request.destination.trim(); const load = request.load_weight_lb; const invalid = Number.isNaN(departure.getTime()) ? 'Enter a valid departure date and time.' : departure.getTime() < now.getTime() ? 'Departure must be now or in the future. Update the date or time and retry.' : !origin ? 'Enter an origin.' : !destination ? 'Enter a destination.' : origin.toLowerCase() === destination.toLowerCase() ? 'Origin and destination must be different.' : !Number.isFinite(load) || load <= 0 ? 'Load weight must be a finite value greater than zero.' : ![10, 25, 50].includes(request.checkpoint_interval_miles) ? 'Choose a 10, 25 or 50 mile checkpoint interval.' : undefined; if (invalid) { setError(invalid); setMobileView('plan'); return; } const sequence = requestSequence.current + 1; requestSequence.current = sequence; abortController.current?.abort(); const controller = new AbortController(); abortController.current = controller; if (updateMessageTimer.current) clearTimeout(updateMessageTimer.current); setLoading(true); setError(undefined); setUpdateMessage(undefined); try { const next = await planRoutes({ ...request, origin, destination, departure_time: departure.toISOString() }, { signal: controller.signal }); if (sequence !== requestSequence.current) return; setResponse(next); setSelectedRouteId(next.recommended_route_id); setSelectedCheckpoint(undefined); setUpdateMessage('Routes updated'); updateMessageTimer.current = setTimeout(() => setUpdateMessage(undefined), 3000); setMobileView('map'); } catch (requestError) { if (sequence !== requestSequence.current || (requestError instanceof DOMException && requestError.name === 'AbortError')) return; const message = requestError instanceof Error ? requestError.message : 'Unable to analyze this corridor.'; setError(message.includes('Denver, CO to Kansas City, MO') ? 'This preview currently supports Denver, CO to Kansas City, MO. Other routes require live routing.' : message); } finally { if (sequence === requestSequence.current) { setLoading(false); abortController.current = undefined; } } };
  useEffect(() => () => { abortController.current?.abort(); if (updateMessageTimer.current) clearTimeout(updateMessageTimer.current); }, []);
  useEffect(() => { if (!error) return; setErrorToast(error); const timer = setTimeout(() => setErrorToast(undefined), 4000); return () => clearTimeout(timer); }, [error]);
  const handleCheckpoint = useCallback((checkpoint?: Checkpoint) => setSelectedCheckpoint(checkpoint), []);
  const handleRouteSelect = useCallback((routeId: string) => { setSelectedRouteId(routeId); setSelectedCheckpoint(undefined); }, []);
  const sheetPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => { sheetDrag.current = { startY: event.clientY, startSnap: sheetSnap }; event.currentTarget.setPointerCapture(event.pointerId); };
  const sheetPointerUp = (event: ReactPointerEvent<HTMLDivElement>) => { if (!sheetDrag.current) return; const delta = event.clientY - sheetDrag.current.startY; const positions = ['collapsed', 'half', 'expanded'] as const; const current = positions.indexOf(sheetDrag.current.startSnap); const next = delta < -45 ? Math.min(2, current + 1) : delta > 45 ? Math.max(0, current - 1) : current; setSheetSnap(positions[next]); sheetDrag.current = undefined; event.currentTarget.releasePointerCapture(event.pointerId); };
  const data = response ?? null;
  const routes = data?.routes ?? [];
  const selectedRoute = routes.find((route) => route.id === selectedRouteId) ?? routes[0];
  const displayRoutes = routes.length ? routes : [];

  return <div className="app-shell">
    <div className="sample-disclosure sample-disclosure-mobile">Sample route data · Denver, CO → Kansas City, MO</div>
    <header className="topbar"><Brand /><div className="trip-summary"><b>{request.origin.split(',')[0]}</b><ArrowRight size={13} /><b>{request.destination.split(',')[0]}</b><span className="summary-divider" />{selectedRoute && <><span>{selectedRoute.distance_miles.toFixed(0)} mi</span><span>{formatDuration(selectedRoute.duration_minutes)}</span><span>ETA {formatTime(selectedRoute.arrival_time)}</span></>}</div><div className="header-actions"><RiskBadge risk={selectedRoute?.overall_risk ?? 'low'} compact /><span className="demo-pill" title="Routes and forecasts shown are sample data for demonstration. Demo mode uses the saved Denver–Kansas City corridor."><Radio size={13} /> Demo data</span></div></header>
    <div className="mobile-context"><span className="eyebrow">{mobileView === 'map' ? 'active corridor' : mobileView}</span><strong>{request.origin} <ArrowRight size={13} /> {request.destination}</strong></div>
    <main className="workspace">
      <aside className={`left-column mobile-sheet ${mobileView === 'plan' ? `mobile-visible sheet-${sheetSnap}` : ''}`}><div className="sheet-handle" role="slider" aria-label="Resize plan panel" aria-valuetext={`${sheetSnap} open`} tabIndex={0} onPointerDown={sheetPointerDown} onPointerUp={sheetPointerUp} /><Planner request={request} setRequest={setRequest} onAnalyze={analyze} loading={loading} />{error && <div className="error-state" role="alert">{error}</div>}</aside>
      <section className={`map-column ${mobileView === 'map' ? 'mobile-visible' : ''}`}><MapCanvas routes={displayRoutes} selectedRoute={selectedRoute} metric={metric} frame={selectedRoute && data?.weather_frames_by_route?.[selectedRoute.id]?.[metric]?.[slider] ? data.weather_frames_by_route[selectedRoute.id][metric][slider] : data?.weather_frames[metric]?.[slider]} selectedCheckpoint={selectedCheckpoint} onCheckpoint={handleCheckpoint} onRouteSelect={handleRouteSelect} />{loading && <div className="analysis-status" role="status" aria-live="polite"><LoaderCircle className="loading-spinner" size={15} aria-hidden="true" />Analyzing routes…</div>}{!loading && updateMessage && <div className="analysis-status success" role="status" aria-live="polite">{updateMessage}</div>}{!loading && errorToast && <div className="analysis-status error" role="alert" aria-live="assertive">{errorToast}</div>}</section>
      <aside className={`right-column ${mobileView === 'routes' || mobileView === 'weather' ? 'mobile-visible' : ''}`}>{data?.safe_route_available === false && <div className="unsafe-banner" role="status">No route is safe under the current forecast. Review no-travel segments before dispatch.</div>}<div className="right-tabs">{([['routes', Route], ['weather', BarChart3], ['checkpoints', Gauge]] as const).map(([key, TabIcon]) => <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}><TabIcon size={14} />{key}</button>)}</div>{tab === 'routes' && <div className="routes-list">{routes.length ? routes.map((route) => <RouteCard key={route.id} route={route} selected={route.id === selectedRoute?.id} onSelect={() => { setSelectedRouteId(route.id); setSelectedCheckpoint(undefined); }} />) : <div className="empty-state"><Route size={22} /><strong>Your corridor is ready to analyze</strong><span>Choose your trip inputs, then compare three weather-aware routes.</span></div>}</div>}{tab === 'weather' && data && <WeatherPanel metric={metric} setMetric={setMetric} slider={slider} setSlider={setSlider} response={data} routeId={selectedRoute?.id} />}{tab === 'checkpoints' && selectedRoute && <CheckpointTable route={selectedRoute} selectedCheckpoint={selectedCheckpoint} onCheckpoint={setSelectedCheckpoint} />}</aside>
    </main>
    <nav className="bottom-nav">{([['map', Navigation], ['routes', Route], ['weather', CloudRain], ['plan', Truck]] as const).map(([key, NavIcon]) => <button key={key} className={mobileView === key ? 'active' : ''} onClick={() => { setMobileView(key); setSheetSnap(key === 'map' ? 'collapsed' : 'half'); if (key === 'routes') setTab('routes'); if (key === 'weather') setTab('weather'); }}><NavIcon size={18} /><span>{key}</span></button>)}</nav>
  </div>;
}

export default App;
