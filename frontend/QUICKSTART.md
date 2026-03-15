# Scriptorium Frontend - Quick Start

## Installation & Setup

### 1. Install Dependencies
```bash
npm install
```

### 2. Start Development Server
```bash
npm run dev
```

Visit `http://localhost:5173` in your browser.

### 3. Backend Configuration

The frontend proxies API calls to `http://localhost:8000` (the FastAPI backend).

Ensure your backend is running:
```bash
# In the backend directory
uvicorn main:app --reload --port 8000
```

## Project Overview

### Architecture

- **Framework**: SvelteKit 5 with Svelte 5 runes
- **Styling**: Tailwind CSS 4
- **Type Safety**: Full TypeScript support
- **API Client**: Custom typed fetch wrapper in `src/lib/api/client.ts`

### Key Files

| File | Purpose |
|------|---------|
| `src/lib/api/client.ts` | API client with all backend endpoints |
| `src/lib/types/index.ts` | TypeScript interfaces for all models |
| `src/lib/components/BookCard.svelte` | Book card component (Svelte 5 runes) |
| `src/lib/components/Sidebar.svelte` | Navigation sidebar with libraries |
| `src/routes/+layout.ts` | Root layout with auth and data loading |
| `src/routes/auth/login/+page.svelte` | Login page |
| `src/routes/auth/register/+page.svelte` | Registration page |
| `src/routes/(app)/library/[id]/+page.svelte` | Library view with books |
| `src/routes/(app)/book/[id]/+page.svelte` | Book detail page with reading progress |

### Routing

The app uses layout groups (`(app)`) to:
- Show sidebar + header for authenticated routes
- Show full-screen auth pages for login/register
- Automatically redirect unauthenticated users to login

```
/                           → Dashboard (requires auth)
/library/[id]               → Library view (requires auth)
/book/[id]                  → Book detail (requires auth)
/shelves                    → Shelves list (requires auth)
/settings                   → User settings (requires auth)
/auth/login                 → Login page
/auth/register              → Registration page
```

## Svelte 5 Runes

This codebase uses Svelte 5's reactive primitives:

### State
```svelte
<script lang="ts">
  let count = $state(0);
</script>
```

### Derived Values
```svelte
<script lang="ts">
  let count = $state(0);
  let doubled = $derived(count * 2);
</script>
```

### Component Props
```svelte
<script lang="ts">
  interface Props {
    title: string;
    count: number;
  }
  const { title, count }: Props = $props();
</script>
```

### Effects
```svelte
<script lang="ts">
  let count = $state(0);
  
  $effect(() => {
    console.log('Count changed:', count);
  });
</script>
```

## Building & Deployment

### Build for Production
```bash
npm run build
```

Output is in the `build/` directory (Node.js adapter).

### Docker
```bash
docker build -t scriptorium-frontend .
docker run -p 3000:3000 scriptorium-frontend
```

### Vite Preview
```bash
npm run preview
```

## Available Scripts

- `npm run dev` - Start dev server with hot reload
- `npm run build` - Build for production
- `npm run preview` - Preview production build locally
- `npm run lint` - Run Svelte type checker
- `npm run format` - Format code with Prettier

## Environment Variables

See `.env.example` for configuration options.

## API Integration

The API client in `src/lib/api/client.ts` provides:

- **Auth**: `login()`, `register()`, `logout()`, `getCurrentUser()`
- **Libraries**: `getLibraries()`, `getLibrary(id)`, `createLibrary()`
- **Books**: `getBooks()`, `getBook(id)`, `createBook()`, `updateBook()`, `deleteBook()`, `searchBooks()`
- **Shelves**: `getShelves()`, `getShelf()`, `createShelf()`, `updateShelf()`, `deleteShelf()`
- **Progress**: `getReadProgress()`, `updateReadProgress()`, `getContinueReading()`

All methods handle authentication automatically via JWT token stored in localStorage.

## Troubleshooting

### "Failed to connect to API"
- Ensure the backend is running on `http://localhost:8000`
- Check that the proxy is correctly configured in `vite.config.ts`

### Auth token not persisting
- Check browser's localStorage (DevTools → Application → Local Storage)
- Ensure `setAuthToken()` is called after successful login

### Svelte 5 component errors
- Verify you're using `$props()` for component props, not old-style props
- Check that `$state` variables are defined at component root
- Use `$derived` instead of computed properties

## Resources

- [Svelte 5 Docs](https://svelte.dev/docs)
- [SvelteKit Docs](https://kit.svelte.dev)
- [Tailwind CSS](https://tailwindcss.com)

## Next Steps

1. Create additional pages (search results, user profiles, etc.)
2. Add book upload/import functionality
3. Implement notification system
4. Add dark mode support
5. Create admin dashboard for managing users and libraries
