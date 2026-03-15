import * as api from '$lib/api/client';

export async function load() {
  const series = await api.getAllSeries(0, 500);
  return { series };
}
