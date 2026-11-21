---
name: generate-asset
description: "Generates a consistent batch of images (illustrations, icons, textures, game visuals, logos) through Codex CLI image generation, reviews them on a contact sheet and converts them to WebP. Use when the user asks to create, generate or replace images or visual assets."
---

# Generate Asset

A consistent image batch, reviewed and integrated into the project. Codex CLI generates with the `gpt-6-luna` model at `high` effort, through its `imagegen` system skill (built-in `image_gen` tool, the user's ChatGPT account: no API key, no per-image billing). Claude scopes the batch, writes the brief, launches, reviews and integrates.

Answer the user, and write every report or deliverable, in the language of the user's request, whatever the language of this skill's files.

Never substitute another model (`gpt-5.6-luna`, `gpt-6-astra`…): if `gpt-6-luna` is refused, stop and say so. Another model, chosen by the user, goes through `CODEX_IMAGE_MODEL=<model>`.

Setup on a machine: `bash ~/.claude/skills/generate-asset/install.sh` (Pillow in `.venv`, Codex CLI check, script smoke test).

## Workflow

1. **Art direction**: never generate without an explicit art direction. Look for it in the project (an "Art direction" section of the README or its equivalent in the project's language, `ART_DIRECTION.md`, `docs/`, `CLAUDE.md`, `assets-src/*/README.md` with previous prompts) and look at 3 or 4 existing assets of the same family. If it covers the need, apply it and say so in one sentence; otherwise ask the questionnaire from [references/brief.md](references/brief.md) in one go, then offer to record the answer in the README.
2. **Scope the batch**: subjects as `id` → concrete visual description (the `id` becomes the file name). Output folder **inside the workdir** passed to Codex (the `workspace-write` sandbox forbids writing elsewhere); in a repository, a source folder such as `assets-src/<batch>/`, not the served folder. Beyond about 20 images, one batch per category, each with its own slug, launched in parallel.
3. **Brief** in `/tmp/<slug>-prompt.md`, in English, following the template in [references/brief.md](references/brief.md). If reference images exist, ask Codex to look at them first.
4. **Launch**:
   ```bash
   mkdir -p <workdir>/<folder>
   ~/.claude/skills/generate-asset/scripts/launch.sh <slug> <workdir> /tmp/<slug>-prompt.md
   ```
   The script detaches Codex (`setsid nohup`), writes the PID to `/tmp/<slug>.pid` and the log to `/tmp/<slug>.log`, and prints the `model:` and `reasoning effort:` lines: check for `gpt-6-luna` and `high`.
5. **Wait without blocking**: Bash with `run_in_background: true`, about 1 minute per image; a Monitor counting the files in the folder tracks progress.
   ```bash
   while kill -0 $(cat /tmp/<slug>.pid) 2>/dev/null; do sleep 15; done; ls <workdir>/<folder>; tail -20 /tmp/<slug>-last.md
   ```
6. **Review**: `python3 ~/.claude/skills/generate-asset/scripts/contact_sheet.py <workdir>/<folder> /tmp/<slug>-sheet.jpg`, read the sheet (consistency, no text, legibility at small size), open doubtful images at full size. To redo or complete: new slug, brief limited to the ids concerned ("generate the N MISSING/REJECTED illustrations (<ids>) — look at the existing files in <folder> first and match their style exactly").
7. **Integrate**: `python3 ~/.claude/skills/generate-asset/scripts/to_webp.py <workdir>/<folder> <served_folder> 768 80` crops to a square, resizes and writes `<id>.webp`, **overwriting** any existing file: replace assets only if the user asked for it. Adapt the display if the format changes (full-bleed scene: `object-fit: cover` as a banner, not a `contain` thumbnail with a shadow).

## Codex pitfalls

- `--approve-for-me` is incompatible with `-s/--sandbox`: use only `-s workspace-write`.
- A `codex exec` started without `setsid` dies when the Claude session restarts: then relaunch only the missing ids.
- Codex first writes to `~/.codex/generated_images/<session>/`: recover the images from there if the copy failed.
- `tmux: Operation not permitted` in the log is harmless.
- Transparency: ask for it explicitly (`transparent background`); Codex preserves the `image_gen` alpha.
- The system skill lives in `~/.codex/skills/.system/imagegen/`. Never switch to CLI/API mode (`~/.codex/skills/.system/imagegen/scripts/image_gen.py`, which requires `OPENAI_API_KEY`) without explicit consent.

## References (read only when the step requires it)

- [references/brief.md](references/brief.md): art direction questionnaire and Codex brief template. Read it when the project's art direction is missing or before writing the brief.
- `scripts/launch.sh`: launches Codex detached; underlying command `codex exec -m gpt-6-luna -c model_reasoning_effort=high -s workspace-write --skip-git-repo-check -C <workdir> -o /tmp/<slug>-last.md "<brief>"`.
- `scripts/contact_sheet.py` (contact sheet), `scripts/to_webp.py` (WebP conversion): usage at the top of each file.
