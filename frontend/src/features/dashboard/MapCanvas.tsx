import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import type { Map, Marker } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Compass, Layers3, Menu, X } from 'lucide-react';
import type { Checkpoint, RiskLevel, RouteOption, WeatherFrame } from '@/types';

const colors: Record<RiskLevel, string> = { low: '#1c8a5b', moderate: '#be8b06', high: '#e56f12', severe: '#d4482e', no_travel: '#151918' };
const routeColors = ['#176b49', '#2c6e9e', '#9b5a2e'];

maplibregl.setWorkerUrl(workerUrl);

function geometry(route: RouteOption) {
  return route.geojson_geometry ?? { type: 'LineString' as const, coordinates: route.geometry.map((point) => [point.x, point.y] as [number, number]) };
}

export default function MapCanvas({ routes, selectedRoute, frame, metric, selectedCheckpoint, onCheckpoint, onRouteSelect }: { routes: RouteOption[]; selectedRoute?: RouteOption; frame?: WeatherFrame; metric: 'wind' | 'rain' | 'snow'; selectedCheckpoint?: Checkpoint; onCheckpoint: (checkpoint?: Checkpoint) => void; onRouteSelect: (routeId: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<Map | undefined>(undefined);
  const markers = useRef<Marker[]>([]);
  const framePoints = useMemo(() => frame?.points ?? [], [frame]);
  const [layersOpen, setLayersOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [showRoutes, setShowRoutes] = useState(true);
  const [showCheckpoints, setShowCheckpoints] = useState(true);
  const [showWeather, setShowWeather] = useState(true);
  const [showLegend, setShowLegend] = useState(true);

  const fitRoutes = useCallback(() => {
    const instance = map.current;
    if (!instance || !routes.length) return;
    const coordinates = routes.flatMap((route) => geometry(route).coordinates);
    if (!coordinates.length) return;
    const bounds = coordinates.reduce((box, coordinate) => box.extend(coordinate as [number, number]), new maplibregl.LngLatBounds(coordinates[0], coordinates[0]));
    instance.fitBounds(bounds, { padding: 60, maxZoom: 7, duration: 500 });
  }, [routes]);

  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') { setLayersOpen(false); setMenuOpen(false); } };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, []);

  useEffect(() => {
    if (!container.current || map.current) return;
    map.current = new maplibregl.Map({
      container: container.current,
      style: { version: 8, sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap contributors' } }, layers: [{ id: 'osm', type: 'raster', source: 'osm' }] },
      center: [-99.8, 39.4], zoom: 5,
    });
    return () => { map.current?.remove(); map.current = undefined; };
  }, []);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const render = () => {
      routes.forEach((route, index) => {
        const sourceId = `route-${route.id}`;
        const source = { type: 'geojson' as const, data: { type: 'Feature' as const, properties: {}, geometry: geometry(route) } };
        if (instance.getSource(sourceId)) (instance.getSource(sourceId) as maplibregl.GeoJSONSource).setData(source.data);
        else { instance.addSource(sourceId, source); instance.addLayer({ id: sourceId, type: 'line', source: sourceId, layout: { visibility: showRoutes ? 'visible' : 'none' }, paint: { 'line-color': route.id === selectedRoute?.id ? routeColors[index] : '#8d9b94', 'line-width': route.id === selectedRoute?.id ? 6 : 3, 'line-opacity': route.id === selectedRoute?.id ? 1 : 0.6 } }); instance.on('click', sourceId, () => onRouteSelect(route.id)); }
        if (instance.getLayer(sourceId)) {
          const selected = route.id === selectedRoute?.id;
          instance.setLayoutProperty(sourceId, 'visibility', showRoutes ? 'visible' : 'none');
          instance.setPaintProperty(sourceId, 'line-color', selected ? routeColors[index] : '#8d9b94');
          instance.setPaintProperty(sourceId, 'line-width', selected ? 6 : 3);
          instance.setPaintProperty(sourceId, 'line-opacity', selected ? 1 : 0.6);
        }
      });
      const heatSource = { type: 'geojson' as const, data: { type: 'FeatureCollection' as const, features: framePoints.map((point) => ({ type: 'Feature' as const, properties: { intensity: point.intensity }, geometry: { type: 'Point' as const, coordinates: [point.x, point.y] } })) } };
      const weatherColors = ['#1c8a5b', '#d4b021', '#e7791b', '#cb3826', '#151918'];
      const weatherColor = ['interpolate', ['linear'], ['get', 'intensity'], 0, weatherColors[0], 0.35, weatherColors[1], 0.7, weatherColors[2], 0.9, weatherColors[3], 1, weatherColors[4]] as unknown as maplibregl.DataDrivenPropertyValueSpecification<string>;
      if (instance.getSource('weather-heat')) (instance.getSource('weather-heat') as maplibregl.GeoJSONSource).setData(heatSource.data);
      else { instance.addSource('weather-heat', heatSource); instance.addLayer({ id: 'weather-heat', type: 'circle', source: 'weather-heat', layout: { visibility: showWeather ? 'visible' : 'none' }, paint: { 'circle-radius': ['interpolate', ['linear'], ['get', 'intensity'], 0, 13, 0.5, 22, 1, 32], 'circle-color': weatherColor, 'circle-opacity': ['interpolate', ['linear'], ['get', 'intensity'], 0, 0.18, 0.5, 0.42, 1, 0.72], 'circle-blur': 0.8 } }); }
      if (instance.getLayer('weather-heat')) { instance.setPaintProperty('weather-heat', 'circle-color', weatherColor); instance.setPaintProperty('weather-heat', 'circle-radius', ['interpolate', ['linear'], ['get', 'intensity'], 0, 13, 0.5, 22, 1, 32]); instance.setPaintProperty('weather-heat', 'circle-opacity', ['interpolate', ['linear'], ['get', 'intensity'], 0, 0.18, 0.5, 0.42, 1, 0.72]); }
      if (instance.getLayer('weather-heat')) instance.setLayoutProperty('weather-heat', 'visibility', showWeather ? 'visible' : 'none');
      routes.forEach((route) => { const routeId = `route-${route.id}`; if (instance.getLayer(routeId)) instance.moveLayer(routeId); });
      markers.current.forEach((marker) => marker.remove()); markers.current = [];
      selectedRoute?.checkpoints.forEach((checkpoint) => {
        const element = document.createElement('button'); element.className = 'checkpoint-marker'; element.style.background = colors[checkpoint.risk_level]; element.setAttribute('aria-label', `Checkpoint mile ${checkpoint.mile}`); element.onclick = () => onCheckpoint(checkpoint);
        if (selectedCheckpoint?.id === checkpoint.id) element.classList.add('active');
        element.style.display = showCheckpoints ? '' : 'none';
        const marker = new maplibregl.Marker({ element }).setLngLat([checkpoint.longitude ?? checkpoint.x, checkpoint.latitude ?? checkpoint.y]).addTo(instance); markers.current.push(marker);
      });
      if (routes.length) {
        fitRoutes();
      }
    };
    if (instance.isStyleLoaded()) render(); else instance.once('load', render);
  }, [routes, selectedRoute, framePoints, metric, selectedCheckpoint, onCheckpoint, onRouteSelect, showRoutes, showCheckpoints, showWeather, fitRoutes]);

  return <div className="map-shell"><div className="map-toolbar"><button onClick={fitRoutes}><Compass size={15} /> Fit corridor</button><div className="map-actions"><div className="map-control-wrap"><button aria-label="Layers" aria-expanded={layersOpen} onClick={() => { setLayersOpen((open) => !open); setMenuOpen(false); }}><Layers3 size={16} /></button>{layersOpen && <div className="map-popover" role="dialog" aria-label="Map layers"><label><input type="checkbox" checked={showRoutes} onChange={(event) => setShowRoutes(event.target.checked)} /> Route lines</label><label><input type="checkbox" checked={showCheckpoints} onChange={(event) => setShowCheckpoints(event.target.checked)} /> Checkpoints</label><label><input type="checkbox" checked={showWeather} onChange={(event) => setShowWeather(event.target.checked)} /> Weather overlay</label><label><input type="checkbox" checked={showLegend} onChange={(event) => setShowLegend(event.target.checked)} /> Weather legend</label></div>}</div><div className="map-control-wrap"><button aria-label="Map controls" aria-expanded={menuOpen} onClick={() => { setMenuOpen((open) => !open); setLayersOpen(false); }}><Menu size={16} /></button>{menuOpen && <div className="map-popover map-menu-popover" role="menu"><button role="menuitem" onClick={() => { fitRoutes(); setMenuOpen(false); }}>Fit routes</button><button role="menuitem" onClick={() => { map.current?.resetNorthPitch(); fitRoutes(); setMenuOpen(false); }}>Reset view</button><button role="menuitem" onClick={() => { setShowLegend((visible) => !visible); setMenuOpen(false); }}>{showLegend ? 'Hide' : 'Show'} legend</button></div>}</div></div></div><div ref={container} className="maplibre-container" role="img" aria-label="Interactive truck route map" /><div className={`map-legend ${showLegend ? '' : 'hidden'}`}><span className="eyebrow">{metric} intensity</span>{(Object.keys(colors) as RiskLevel[]).map((risk) => <div key={risk}><i style={{ backgroundColor: colors[risk] }} />{risk.replace('_', ' ')}</div>)}<span className="simulated-label">Simulated weather · risk is load-adjusted</span></div>{selectedCheckpoint && <div className="checkpoint-popover"><button onClick={() => onCheckpoint(undefined)} aria-label="Close checkpoint"><X size={15} /></button><span className="eyebrow">checkpoint / mile {selectedCheckpoint.mile.toFixed(1)}</span><strong>{new Date(selectedCheckpoint.arrival_time).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })} arrival</strong><div className="checkpoint-weather"><span>Wind <b>{selectedCheckpoint.wind_mph.toFixed(1)} mph</b></span><span>Rain <b>{selectedCheckpoint.rainfall_in_hr.toFixed(2)} in/hr</b></span><span>Snow <b>{selectedCheckpoint.snowfall_in_hr.toFixed(2)} in/hr</b></span></div><div className="checkpoint-risk"><span>Risk</span><b style={{ color: colors[selectedCheckpoint.risk_level] }}>{selectedCheckpoint.risk_level.replace('_', ' ')}</b></div>{(selectedCheckpoint.longitude !== undefined && selectedCheckpoint.latitude !== undefined) && <span><b>{selectedCheckpoint.longitude.toFixed(3)}, {selectedCheckpoint.latitude.toFixed(3)}</b></span>}</div>}</div>;
}
