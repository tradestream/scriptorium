import * as api from '$lib/api/client';

export async function load() {
  const [series, libraries] = await Promise.all([
    api.getAllSeries(0, 500),
    api.getLibraries(),
  ]);
  return { series, libraries };
}
