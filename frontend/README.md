# Scriptorium Frontend

A SvelteKit 5 + Svelte 5 frontend for the Scriptorium self-hosted book and comics library server.

## Features

- Clean, responsive interface built with Svelte 5 runes
- Tailwind CSS 4 styling
- TypeScript for type safety
- Book management with covers, metadata, and reading progress
- Library organization and shelving system
- Authentication (login/register)
- Dashboard with recent additions and continue reading

## Project Structure

```
src/
├── lib/
│   ├── api/
│   │   └── client.ts        # API client for FastAPI backend
│   ├── components/
│   │   ├── BookCard.svelte  # Individual book card
│   │   ├── BookGrid.svelte  # Responsive grid layout
│   │   ├── Header.svelte    # Top navigation bar
│   │   └── Sidebar.svelte   # Left sidebar navigation
│   └── types/
│       └── index.ts         # TypeScript interfaces
├── routes/
│   ├── auth/
│   │   ├── login/           # Login page
│   │   └── register/        # Registration page
│   ├── (app)/
│   │   ├── library/[id]/    # Library view
│   │   ├── book/[id]/       # Book detail page
│   │   ├── shelves/         # Shelves list
│   │   ├── settings/        # User settings
│   │   └── +layout.svelte   # App layout wrapper
│   ├── +layout.svelte       # Root layout
│   ├── +layout.ts           # Layout data loading
│   ├── +page.svelte         # Dashboard
│   └── +page.ts             # Dashboard data loading
└── app.html                 # HTML shell
```

## Getting Started

### Prerequisites
- Node.js 18+
- npm or yarn

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

Visit `http://localhost:5173` in your browser.

The frontend expects the FastAPI backend to be running at `http://localhost:8000`.

### Building

```bash
npm run build
npm run preview
```

## API Configuration

The API base URL is configurable in `src/lib/api/client.ts`. By default it uses `/api` which proxies to the backend at `localhost:8000` via Vite's proxy configuration.

## Svelte 5 Runes

This project uses Svelte 5's new reactive primitives:

- `$state` - Reactive state declarations
- `$derived` - Computed/derived values
- `$props` - Component props
- `$effect` - Side effects
- `$watch` - Watched values

Example:
```svelte
<script lang="ts">
  let count = $state(0);
  let doubled = $derived(count * 2);

  function increment() {
    count++;
  }
</script>
```

## Tailwind CSS

Styling uses Tailwind CSS 4 with utility-first approach. Custom colors and theme extensions are in `tailwind.config.ts`.

## License

See LICENSE in parent project.
