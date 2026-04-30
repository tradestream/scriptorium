import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

const VALID_SECTIONS = new Set(['account', 'library', 'metadata', 'files', 'integrations', 'system']);

export const load: PageLoad = async ({ url }) => {
  const section = url.searchParams.get('section');
  const target = section && VALID_SECTIONS.has(section) ? section : 'account';
  redirect(302, `/settings/${target}`);
};
