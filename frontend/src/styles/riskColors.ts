import type { RiskLevel } from '@/types';

export const riskColors: Record<RiskLevel, string> = {
  low: '#00B8FF', moderate: '#FFD000', high: '#ff8a00', severe: '#ff3030', no_travel: '#101514',
};
export const riskBackgrounds: Record<RiskLevel, string> = {
  low: '#e0f6ff', moderate: '#fff8cf', high: '#fff0df', severe: '#ffebe7', no_travel: '#e8eae8',
};
export const riskLabels: Record<RiskLevel, string> = {
  low: 'Low', moderate: 'Moderate', high: 'High', severe: 'Severe', no_travel: 'No travel',
};
