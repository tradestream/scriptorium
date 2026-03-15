import * as api from '$lib/api/client';

export async function load({ params }: { params: { id: string } }) {
  const result = await api.getSeriesBooks(params.id);
  return result;
}
