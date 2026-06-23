# suno-maker — Automated Suno AI music generation for headless Linux servers

> Generate Suno songs on a Linux server with no monitor — Xvfb runs Chrome headlessly, and Claude/Gemini API solves the hCaptcha automatically.

[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Skill-blueviolet)](https://github.com/NachaFromMars)

## Overview
suno-maker automates Suno AI music generation on headless Linux servers. It uses Xvfb Virtual Display to run Chrome in GUI mode without a physical monitor, bypassing Google's anti-automation detection. hCaptcha is solved automatically by the Claude/Anthropic API (Gemini as fallback). Two core functions: Google OAuth login and song creation (custom lyrics + style + download).

## Features
- **Headless Linux** — Xvfb Virtual Display, no monitor needed
- **Anti-detection** — GUI mode via Xvfb, not headless Chrome flags
- **Auto captcha** — Claude API (primary) or Gemini API (fallback) for hCaptcha
- **Two functions** — Account Login (Google OAuth) + Song Creation (lyrics + style + download)
- **Prerequisite check** — `check_env.sh` → 0 (OK), 1 (install needed), 2 (not logged in)

## Usage / Quick Start
```bash
# Check environment first
bash suno-headless/check_env.sh
# 0 = ready, 1 = install deps, 2 = login needed
```
Requires: `google-chrome`, `Xvfb`

## Trigger Keywords (OpenClaw)
suno headless, suno server, automated suno, suno linux, suno song generation, suno download

## Related Skills
- [suno-automation](https://github.com/NachaFromMars/suno-automation) — browser-based alternative (OpenClaw managed browser)

---
Part of the [NachaFromMars](https://github.com/NachaFromMars) OpenClaw skill ecosystem.
