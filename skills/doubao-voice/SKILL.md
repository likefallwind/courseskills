---
name: doubao-voice
description: Use when generating speech audio with official Doubao/豆包 Seed TTS voices through an API Gateway backed by Agent Plan.
---

# Doubao Voice

## Overview

Use `scripts/doubao_voice.py` to turn text into speech with an official Doubao speaker. The CLI needs only Python 3 and one Gateway client token; provider credentials and Agent Plan protocol conversion stay in the Gateway.

Voice cloning is intentionally out of scope: it requires a separately authorized Speech API key and billing, not just Agent Plan. Do not attempt clone registration, status queries, cloned-voice synthesis, or provider-direct requests from this skill.

## Setup

The client reads `DOUBAO_VOICE_GATEWAY_API_KEY` first and then the existing `API_GATEWAY` environment variable. If `API_GATEWAY` is already exported for a speech-capable Gateway, no additional credential variable is needed. This is only a credential alias: a chat-only Gateway is not sufficient, even when its token is valid. The configured service must expose `/v1/audio/speech`; do not fall back to `/v1/chat/completions` for TTS.

```bash
# Optional overrides:
export DOUBAO_VOICE_GATEWAY_API_KEY=<one client token from GATEWAY_KEYS>
export DOUBAO_VOICE_GATEWAY_BASE_URL=http://127.0.0.1:8111  # /v1 is also accepted
```

The CLI does not read `.env` or shell startup files. Confirm the Gateway exposes `/v1/audio/speech`; do not substitute `/v1/chat/completions` or a provider endpoint.

## Choose a Voice

Read [references/voices.md](references/voices.md) for curated Chinese options. For a male teacher or lecture narrator, default to **渊博小叔 2.0** (`zh_male_yuanboxiaoshu_uranus_bigtts`) when the user has no preference; offer **儒雅逸辰 2.0** (`zh_male_ruyayichen_uranus_bigtts`, officially listed for 视频配音) and **儒雅青年 2.0** (`zh_male_ruyaqingnian_uranus_bigtts`) as alternatives. Start at speed `1.0` and generate one short sample before batch synthesis.

Check the [official voice list](https://docs.volcengine.com/docs/doubao-voice/tone-list-3?lang=zh) when updating options or using an ID not in the curated reference. Use the “豆包语音合成模型2.0” group; do not mix in real-time-speech, voice-cloning, or legacy model voices. `--voice` intentionally accepts new official IDs rather than a fixed enum.

## Generate Speech

If none was supplied, select from the curated reference for the stated scenario or ask for an official Doubao speaker ID. Do not substitute OpenAI names such as `alloy`.

```bash
python skills/doubao-voice/scripts/doubao_voice.py speak \
  --text-file '/tmp/course scripts/intro.txt' \
  --voice zh_male_yuanboxiaoshu_uranus_bigtts \
  --output '/tmp/course audio/intro.mp3' \
  --format mp3 --sample-rate 24000 --speed 1.0
```

`--text` and `--text-file` are mutually exclusive. Formats are `mp3`, `wav`, `pcm`, and `ogg_opus`; speed is 0.5–2.0; sample rates are 8000/16000/22050/24000/32000/44100/48000, with OGG Opus requiring 48000 Hz.

Existing outputs are skipped without a network request, even if credentials are absent. Use `--force` only when the user explicitly approves regeneration and additional usage. Responses are Content-Type checked, and audio is written atomically only after success; failures never leave partial files. Commands never retry automatically.

If `AgentPlanDeductNotEnabled` appears, enable Agent Plan deduction for the account/seat. Keep “超额后付费” disabled unless overage charges are explicitly accepted. Never work around errors with another provider endpoint or credential.

## Quick Reference

```bash
python skills/doubao-voice/scripts/doubao_voice.py --help
python skills/doubao-voice/scripts/doubao_voice.py speak --help
python -m unittest discover -s skills/doubao-voice/tests -v
```

## Common Mistakes

| Stop condition | Correct action |
|---|---|
| Using an OpenAI voice name or `/v1/chat/completions` | Use an official Doubao speaker and `/v1/audio/speech` |
| Client command contains a provider host, upstream key, or resource override | Use only the configured Gateway and Gateway token |
| Treating HTTP 200 or nonempty bytes as audio | Validate the expected audio Content-Type |
| Auto-retrying, streaming partial output, or overwriting an approved take | Stop, preserve the old file, and require explicit approval plus `--force` |
| Printing raw responses or credentials | Print only safe status fields and request IDs |

Keep generated audio outside the skill directory. Before finishing, inspect `git status`; do not commit generated media.
