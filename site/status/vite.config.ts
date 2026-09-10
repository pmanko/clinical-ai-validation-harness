import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  root: __dirname,
  base: './',
  plugins: [react()],
  server: { host: '127.0.0.1', port: 4322, strictPort: true, fs: { allow: [path.resolve(__dirname, '../..')] } },
  build: { outDir: 'dist', emptyOutDir: true },
});
