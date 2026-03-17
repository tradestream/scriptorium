import * as api from '$lib/api/client';

export async function load({ params }: { params: { id: string } }) {
  const article = await api.getArticle(Number(params.id));
  return { article };
}
