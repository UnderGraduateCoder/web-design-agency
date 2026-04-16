#!/usr/bin/env node
/**
 * Wrapper that loads .env and starts the 21st.dev Magic MCP server.
 * Keeps API keys out of settings.json and process args.
 */
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// Load .env from project root (two levels up from .claude/helpers/)
const envPath = path.resolve(__dirname, '../../.env');
if (fs.existsSync(envPath)) {
  fs.readFileSync(envPath, 'utf8').split('\n').forEach(line => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) return;
    const idx = trimmed.indexOf('=');
    if (idx < 1) return;
    const key = trimmed.substring(0, idx).trim();
    const val = trimmed.substring(idx + 1).trim().replace(/^["']|["']$/g, '');
    if (!process.env[key]) process.env[key] = val;
  });
}

const apiKey = process.env['21ST_API_KEY'];
if (!apiKey) {
  process.stderr.write('Error: 21ST_API_KEY not found in .env\n');
  process.exit(1);
}

const isWin = process.platform === 'win32';
const child = spawn(
  isWin ? 'cmd' : 'npx',
  isWin
    ? ['/c', 'npx', '-y', '@21st-dev/magic@latest', `API_KEY=${apiKey}`]
    : ['-y', '@21st-dev/magic@latest', `API_KEY=${apiKey}`],
  { stdio: 'inherit', env: process.env }
);

child.on('exit', code => process.exit(code || 0));
