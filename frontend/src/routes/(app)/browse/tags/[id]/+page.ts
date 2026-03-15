import * as api from '$lib/api/client';

export async function load({ params }: { params: { id: string } }) {
  const result = await api.getTagBooks(params.id);
  return result;
}
