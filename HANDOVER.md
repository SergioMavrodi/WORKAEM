# Handover: вирусные реакции (WORKAEM)

Это передача контекста для нового чата. Сначала прочитай этот файл, потом `.claude/skills/reaction-video/SKILL.md`.

## Цель пользователя
Делать вирусные «безликие» реакции на ролики (Roblox-истории типа «In This Town»).
Пользователь будет присылать вертикальные ролики, на каждый нужна готовая реакция.

## Решения, которые пользователь уже принял
- **Выход:** 16:9 (YouTube), как у YXL Salah.
- **Исходник:** вертикальный 9:16. Он стоит по центру чуть левее (`video_x: 0.42`), по бокам размытый фон.
- **Реактор:** один (девушку убрали). Мультяшный, стоит справа (`size: 0.62`).
- **Стиль персонажа: Roblox** (сказано в последнем сообщении). Сейчас в шаблоне
  нарисованный Max (`make_avatars.py`), его нужно заменить на персонажа в стиле Roblox.
  Пользователь предлагал скачать для этого скилл. Спроси, какой именно, или нарисуй сам:
  блочная голова, лицо-«наклейка», состояния idle/talk/shock, PNG 600x600 с прозрачностью.
- **Язык:** английский. **Голос:** AI (Piper, `en_US-ryan-high`, `length_scale` ≈ 0.88).
- **Подача:** скопировать манеру YXL Salah: зумы, ритм реакций, стиль речи.
  Пользователь просил разобрать первые 1–2 минуты его ролика.
  Если YXL зумит и во время воспроизведения (не только на паузах), я предложил добавить такой режим.
  Ответа пока не было.

## Ссылки
| Что | Ссылка |
|---|---|
| Референс подачи (главный) | https://youtu.be/9TJxC5rEq_c: «In This Town Roblox TikToks Got WORSE \| YXL Salah» (@yxlsalahlive), сольный стример с лицом в кадре |
| Референс формата (первый) | https://youtu.be/wlQl8iOEcjo: «IN THIS TOWN Roblox Compilation But Things Get CRAZY... \| REACTION» (They All Laughed) |
| Первый ролик для реакции (16:9, может уже не нужен) | https://www.youtube.com/watch?v=CB2aoMPP2dU: «In This Town Roblox Stories Compilation (#1)» (TeamDeam) |

## Что сделано (ветка `claude/beautiful-allen-27cx2u`, запушена)
Скилл `.claude/skills/reaction-video/`:
- `scripts/setup.sh`: ставит piper-tts, faster-whisper, pillow и скачивает голоса Piper в `~/.cache/reaction-video/voices`.
- `scripts/inspect_source.py`: листы кадров 4x3 с таймкодами и транскрипт Whisper (word timestamps).
- `scripts/style_stats.py`: цифры стиля по транскрипту (темп, частота реплик, n-граммы, паузы).
- `scripts/build.py`: сборка видео.
  - Паузы: стоп-кадр, панч-зум в `focus`, виньетка.
  - Реплики поверх видео, оригинал под ними приглушается.
  - Хук в начале, вырезка кусков.
  - Аватар открывает рот по громкости своей реплики и подпрыгивает, есть лицо `shock`.
  - ASS-субтитры (Luckiest Guy) стоят по центру ролика.
  - SFX синтезируются: boom/ding/whoosh/pop/riser.
  - Громкость −14 LUFS. Режим `--preview` для быстрой проверки.
- `scripts/thumbnail.py`: превью: кадр, реактор, огромный текст (`*слово*` выделяется красным), стрелка.
- `scripts/make_avatars.py`: мультяшные аватары (временно, будет Roblox-стиль).
- `reference/schema.md`: формат reaction.json. `reference/viral-format.md`: правила формата.
- `reference/styles/`: `_template.md` (заполнить для YXL → `yxl-salah.md`), `solo-streamer.md`
  (общий профиль, НЕ копия YXL), `duo-hype.md`.
- `reactions/_template/`: шаблон проекта (reaction.json под соло-раскладку, аватары Max).

Всё проверено на синтетическом тестовом ролике, на реальных роликах ещё не запускалось.
Тестовая сборка 40 с идёт около минуты в 1080p и около 30 с в preview.

## Блокеры
1. **YouTube не отдаёт видео в облачный контейнер** (yt-dlp: «Sign in to confirm you're not a bot»).
   Обходить это нельзя: попытку подменить player_client отклонил классификатор. Работают oEmbed и превью с i.ytimg.com.
2. **Ролик YXL пользователь скачал к себе на компьютер, в папку «CapCut для Claude».**
   Из облачной сессии её не видно: list_computer_folders пустой, компьютер не подключён.
   Варианты:
   - прикрепить mp4 прямо в чат;
   - открыть сессию на своём компьютере (Claude Desktop или `claude remote-control` в нужной папке);
   - подключить папку через Remote Control (Claude Desktop → Settings → Claude Code → Remote Control);
   - положить файл в репозиторий. mp4 в `reactions/*/input` и `style_ref` попадают под gitignore, лимит GitHub 100 МБ.

## Следующие шаги
1. Получить ролик YXL. Положить его в `reactions/<slug>/style_ref/ref.mp4` и запустить:
   ```bash
   python3 .claude/skills/reaction-video/scripts/inspect_source.py style_ref/ref.mp4 work/style --every 2 --whisper small --lang en
   ```
   ```bash
   python3 .claude/skills/reaction-video/scripts/style_stats.py work/style/transcript.json
   ```
   Разобрать первые 1–2 минуты по листам кадров (лучше `--every 1` на этом отрезке):
   - как часто он останавливает видео;
   - куда и насколько зумит, как быстро;
   - зумит ли во время воспроизведения;
   - на чём и как зумит своё лицо;
   - длина одной реакции, фразы и приёмы.

   Заполнить `reference/styles/yxl-salah.md`. Если найдутся новые типы зумов, добавить их в `build.py`
   (например, медленный наезд во время воспроизведения или зум на реактора).
2. Сделать аватар в стиле Roblox (idle/talk/shock), положить в `reactions/_template/avatars/`.
3. Когда пользователь пришлёт ролик: скопировать `_template` в `reactions/<slug>/`, сделать inspect, написать
   reaction.json в стиле YXL, собрать `--preview`, проверить кадры, собрать финал, сделать thumbnail
   и `out/post.md` (3 названия, описание с указанием автора оригинала, таймкоды, теги).
4. Переписка с пользователем на русском, коротко и по делу. Перед крупными решениями задавать вопросы,
   пользователь сам об этом просил.

## Окружение
- Linux, ffmpeg есть, Chromium/Playwright есть. edge-tts не работает: прокси не пропускает WebSocket, поэтому Piper.
- faster-whisper: аудио декодируется через ffmpeg в numpy, потому что PyAV несовместим с `metadata_errors`.
- Голоса и модели не коммитятся, setup.sh скачивает их заново.
