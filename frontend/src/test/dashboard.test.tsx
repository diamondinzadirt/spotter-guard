import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { RoutePlanRequest, RoutePlanResponse } from '@/types';
import { App } from '@/features/dashboard/SpotterDashboard';

const { planRoutes } = vi.hoisted(() => ({ planRoutes: vi.fn<(request: RoutePlanRequest) => Promise<RoutePlanResponse>>() }));

vi.mock('@/services/mockApi', () => ({ planRoutes }));
vi.mock('@/features/dashboard/MapCanvas', () => ({ default: () => <div aria-label="Interactive truck route map" /> }));

const route = (interval: number): RoutePlanResponse => ({
  routes: [{ id: 'i70-central', name: 'I-70 Central', description: 'Test route', distance_miles: 100, duration_minutes: 120, arrival_time: '2026-10-23T14:00:00Z', departure_time: '2026-10-23T12:00:00Z', overall_risk: 'low', severe_miles: 0, high_miles: 0, no_travel_miles: 0, average_risk: 0, recommended: true, geometry: [{ x: -105, y: 39 }, { x: -100, y: 39 }], geojson_geometry: { type: 'LineString', coordinates: [[-105, 39], [-100, 39]] }, checkpoints: [0, interval, interval * 2].map((mile) => ({ id: `cp-${interval}-${mile}`, mile, arrival_time: '2026-10-23T12:30:00Z', wind_mph: 20, rainfall_in_hr: 0, snowfall_in_hr: 0, risk_level: 'low', x: -105 + mile / 20, y: 39 })) , risk_segments: [] }], recommended_route_id: 'i70-central', weather_frames: { wind: [], rain: [], snow: [] }, data_source: 'demo', safe_route_available: true,
});

const chooseInterval = async (user: ReturnType<typeof userEvent.setup>, value: '10' | '25' | '50') => user.click(screen.getAllByRole('button', { name: new RegExp(`^${value} mi$`) })[0]);
const analyzeButton = () => screen.getAllByRole('button', { name: /^Analyze routes$/ })[0];
const setNativeInputValue = (input: HTMLInputElement, value: string) => {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  setter?.call(input, value);
  fireEvent.input(input, { target: { value } });
  fireEvent.change(input, { target: { value } });
};
const fillValidJourney = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.selectOptions(screen.getByLabelText('Starting State'), 'GA');
  await user.type(screen.getByLabelText('Starting City'), 'Atlanta');
  await user.selectOptions(screen.getByLabelText('Destination State'), 'TN');
  await user.type(screen.getByLabelText('Destination City'), 'Memphis');
  setNativeInputValue(screen.getByLabelText(/Departure date/i), '2099-01-01');
  await waitFor(() => expect(screen.getByLabelText(/Departure date/i)).toHaveValue('2099-01-01'));
  setNativeInputValue(screen.getByLabelText(/Departure time/i), '12:00');
  await waitFor(() => expect(screen.getByLabelText(/Departure time/i)).toHaveValue('12:00'));
  await user.type(screen.getByLabelText(/Load weight/i), '42000');
};

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('Analyze Routes workflow', () => {
  it('shows pending feedback, prevents duplicates, and renders fresh results', async () => {
    const user = userEvent.setup();
    let resolveRequest!: (response: RoutePlanResponse) => void;
    planRoutes.mockReturnValueOnce(new Promise((resolve) => { resolveRequest = resolve; }));
    render(<App />);
    await fillValidJourney(user);
    const analyze = screen.getByRole('button', { name: /^Analyze routes$/ });
    await user.click(analyze);
    expect(screen.getByRole('button', { name: /Analyzing routes/i })).toBeDisabled();
    await user.click(analyze);
    expect(planRoutes).toHaveBeenCalledTimes(1);
    resolveRequest(route(10));
    await user.click(screen.getByRole('button', { name: /^checkpoints$/ }));
    expect(await screen.findByText('10.0')).toBeInTheDocument();
    expect(screen.getByText('Routes updated')).toBeInTheDocument();
  });

  it('submits 10, 25, 50 and 10 mile analyses without stale checkpoints', async () => {
    const user = userEvent.setup();
    planRoutes.mockImplementation(async (request) => route(request.checkpoint_interval_miles));
    render(<App />);
    await fillValidJourney(user);
    for (const interval of ['10', '25', '50', '10'] as const) {
      await chooseInterval(user, interval);
      await user.click(analyzeButton());
      await user.click(screen.getAllByRole('button', { name: /^checkpoints$/ })[0]);
      await waitFor(() => expect(screen.getByText(`${interval}.0`)).toBeInTheDocument());
      expect(planRoutes.mock.lastCall?.[0].checkpoint_interval_miles).toBe(Number(interval));
    }
    expect(screen.queryByText('25.0')).not.toBeInTheDocument();
  });

  it('shows a visible expired-departure error without making a request', async () => {
    const user = userEvent.setup();
    render(<App />);
    await fillValidJourney(user);
    setNativeInputValue(screen.getAllByLabelText(/Departure date/i)[0] as HTMLInputElement, '2020-01-01');
    await waitFor(() => expect(screen.getAllByLabelText(/Departure date/i)[0]).toHaveValue('2020-01-01'));
    setNativeInputValue(screen.getAllByLabelText(/Departure time/i)[0] as HTMLInputElement, '00:00');
    await waitFor(() => expect(screen.getAllByLabelText(/Departure time/i)[0]).toHaveValue('00:00'));
    await user.click(analyzeButton());
    expect((await screen.findAllByRole('alert'))[0]).toHaveTextContent(/future/i);
    expect(planRoutes).not.toHaveBeenCalled();
  });

  it('stops loading and supports retry after an API failure', async () => {
    const user = userEvent.setup();
    planRoutes.mockRejectedValueOnce(new Error('Unable to reach the route-planning service.')).mockResolvedValueOnce(route(25));
    render(<App />);
    await fillValidJourney(user);
    await user.click(analyzeButton());
    expect((await screen.findAllByRole('alert'))[0]).toHaveTextContent(/Unable to reach/i);
    await user.click(analyzeButton());
    await user.click(screen.getAllByRole('button', { name: /^checkpoints$/ })[0]);
    expect(await screen.findByText('25.0')).toBeInTheDocument();
    expect(planRoutes).toHaveBeenCalledTimes(2);
  });
});
