# Doubao Voice Options

Official source: [豆包语音音色列表](https://docs.volcengine.com/docs/doubao-voice/tone-list-3?lang=zh), section **“豆包语音合成模型2.0、S2S-O2.0、S2S-全双工”音色列表**.

Verified against the rendered official table on 2026-11-22. The CLI uses model `doubao-seed-tts-2.0`; account/Gateway availability still needs a real synthesis request to confirm.

## Recommended Chinese voices

| Name | `voice_type` / speaker ID | Official scene | Suggested use |
|---|---|---|---|
| 渊博小叔 2.0 | `zh_male_yuanboxiaoshu_uranus_bigtts` | 通用场景 | Default male voice for lecture/course narration |
| 儒雅逸辰 2.0 | `zh_male_ruyayichen_uranus_bigtts` | 视频配音 | Alternative male voice for polished course videos |
| 儒雅青年 2.0 | `zh_male_ruyaqingnian_uranus_bigtts` | 通用场景 | Younger male lecture voice |
| 云舟 2.0 | `zh_male_m191_uranus_bigtts` | 通用场景 | Male voice with Chinese dialect support listed officially |
| 知性女声 2.0 | `zh_female_zhixingnv_uranus_bigtts` | 通用场景 | Female lecture/course narration |
| 亲切女声 2.0 | `zh_female_qinqienv_uranus_bigtts` | 通用场景 | Conversational instruction and explainers |
| Vivi 2.0 | `zh_female_vv_uranus_bigtts` | 通用场景 | Multilingual or Chinese-dialect narration |
| 小何 2.0 | `zh_female_xiaohe_uranus_bigtts` | 通用场景 | General female narration with dialect support listed officially |

The official table labels these voices with scenes such as “通用场景” and “视频配音”, and lists “指令遵循” support. The lecture recommendations above are repository defaults, not official certification as teacher voices.

For a male teacher, start with **渊博小叔 2.0** at speed `1.0`. If the user wants a more formal video-narration style, offer **儒雅逸辰 2.0**; for a younger sound, offer **儒雅青年 2.0**. Generate one short sample before batch synthesis.

## Updating this list

1. Open the official source and use the model-2.0 section, not the real-time-speech, voice-cloning, or legacy model tables.
2. Copy the exact `voice_type`; do not construct IDs from display names or substitute `_moon_`, `_mars_`, `_jupiter_`, or `_saturn_` variants.
3. Update the official scene and capability columns when they change. Keep repository recommendations separate from official descriptions.
4. Do not turn the CLI's `--voice` argument into a fixed enum: this curated table is not the complete catalog, and newly released official IDs should remain usable.
