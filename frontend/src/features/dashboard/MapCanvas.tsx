import { useEffect, useMemo, useRef } from 'react';
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

export default function MapCanvas({ routes, selectedRoute, frame, selectedCheckpoint, onCheckpoint }: { routes: RouteOption[]; selectedRoute?: RouteOption; frame?: WeatherFrame; selectedCheckpoint?: Checkpoint; onCheckpoint: (checkpoint?: Checkpoint) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<Map | undefined>(undefined);
  const markers = useRef<Marker[]>([]);
  const framePoints = useMemo(() => frame?.points ?? [], [frame]);

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
        else { instance.addSource(sourceId, source); instance.addLayer({ id: sourceId, type: 'line', source: sourceId, paint: { 'line-color': route.id === selectedRoute?.id ? routeColors[index] : '#8d9b94', 'line-width': route.id === selectedRoute?.id ? 6 : 3, 'line-opacity': route.id === selectedRoute?.id ? 1 : 0.6 } }); }
      });
      const heatSource = { type: 'geojson' as const, data: { type: 'FeatureCollection' as const, features: framePoints.map((point) => ({ type: 'Feature' as const, properties: { intensity: point.intensity }, geometry: { type: 'Point' as const, coordinates: [point.x, point.y] } })) } };
      if (instance.getSource('weather-heat')) (instance.getSource('weather-heat') as maplibregl.GeoJSONSource).setData(heatSource.data);
      else { instance.addSource('weather-heat', heatSource); instance.addLayer({ id: 'weather-heat', type: 'circle', source: 'weather-heat', paint: { 'circle-radius': 22, 'circle-color': '#4c8fb0', 'circle-opacity': ['interpolate', ['linear'], ['get', 'intensity'], 0, 0.08, 1, 0.35], 'circle-blur': 1 } }); }
      markers.current.forEach((marker) => marker.remove()); markers.current = [];
      selectedRoute?.checkpoints.forEach((checkpoint) => {
        const element = document.createElement('button'); element.className = 'checkpoint-marker'; element.style.background = colors[checkpoint.risk_level]; element.setAttribute('aria-label', `Checkpoint mile ${checkpoint.mile}`); element.onclick = () => onCheckpoint(checkpoint);
        if (selectedCheckpoint?.id === checkpoint.id) element.classList.add('active');
        const marker = new maplibregl.Marker({ element }).setLngLat([checkpoint.longitude ?? checkpoint.x, checkpoint.latitude ?? checkpoint.y]).addTo(instance); markers.current.push(marker);
      });
      if (routes.length) {
        const coordinates = routes.flatMap((route) => geometry(route).coordinates);
        const bounds = coordinates.reduce((box, coordinate) => box.extend(coordinate as [number, number]), new maplibregl.LngLatBounds(coordinates[0], coordinates[0]));
        instance.fitBounds(bounds, { padding: 60, maxZoom: 7, duration: 500 });
      }
    };
    if (instance.isStyleLoaded()) render(); else instance.once('load', render);
  }, [routes, selectedRoute, selectedCheckpoint, framePoints, onCheckpoint]);

  return <div className="map-shell"><div className="map-toolbar"><button onClick={() => map.current?.fitBounds(new maplibregl.LngLatBounds([-105, 37], [-94, 42]), { padding: 50 })}><Compass size={15} /> Fit corridor</button><div className="map-actions"><button aria-label="Layers"><Layers3 size={16} /></button><button aria-label="Map settings"><Menu size={16} /></button></div></div><div ref={container} className="maplibre-container" role="img" aria-label="Interactive truck route map" /><div className="map-legend"><span className="eyebrow">segment risk</span>{(Object.keys(colors) as RiskLevel[]).map((risk) => <div key={risk}><i style={{ backgroundColor: colors[risk] }} />{risk.replace('_', ' ')}</div>)}<span className="simulated-label">Weather layer: simulated</span></div>{selectedCheckpoint && <div className="checkpoint-popover"><button onClick={() => onCheckpoint(undefined)} aria-label="Close checkpoint"><X size={15} /></button><span className="eyebrow">checkpoint / mile {selectedCheckpoint.mile}</span><strong>{new Date(selectedCheckpoint.arrival_time).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })} arrival</strong><div><span>{selectedCheckpoint.wind_mph} mph wind</span><span>{selectedCheckpoint.rainfall_in_hr.toFixed(2)} in/hr rain</span></div><span><b>{selectedCheckpoint.longitude?.toFixed(3)}, {selectedCheckpoint.latitude?.toFixed(3)}</b></span></div>}</div>;
}
