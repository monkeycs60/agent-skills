---
name: generate-asset
description: "Generates a consistent batch of images (illustrations, icons, textures, game visuals, logos) through Codex CLI image generation, reviews them on a contact sheet and converts them to WebP. Use when the user asks to create, generate or replace images or visual assets."
---

# Generate Asset

Un lot d'images cohérent, contrôlé et intégré au projet. Codex CLI génère avec le modèle `gpt-6-luna`, effort `high`, via son skill système `imagegen` (outil intégré `image_gen`, compte ChatGPT de l'utilisateur : ni clé API ni facturation à l'image). Claude cadre, rédige le brief, lance, contrôle et intègre.

Ne jamais substituer un autre modèle (`gpt-5.6-luna`, `gpt-6-astra`…) : si `gpt-6-luna` est refusé, s'arrêter et le signaler. Un autre modèle, choisi par l'utilisateur, passe par `CODEX_IMAGE_MODEL=<modèle>`.

Installation sur une machine : `bash ~/.claude/skills/generate-asset/install.sh` (Pillow dans `.venv`, vérification de Codex CLI, essai des scripts).

## Workflow

1. **Direction artistique** : jamais de génération sans DA explicite. La chercher dans le projet (section « Direction artistique » du README, `ART_DIRECTION.md`, `docs/`, `CLAUDE.md`, `assets-src/*/README.md` avec les prompts précédents) et regarder 3 ou 4 assets existants de la même famille. Si elle couvre le besoin, l'appliquer et le dire en une phrase ; sinon poser le questionnaire de [references/brief.md](references/brief.md) en une seule fois, puis proposer de consigner la réponse dans le README.
2. **Cadrer le lot** : sujets en `id` → description visuelle concrète (l'`id` devient le nom de fichier). Dossier de sortie **dans le workdir** passé à Codex (le sandbox `workspace-write` interdit d'écrire ailleurs) ; dans un dépôt, un dossier de sources comme `assets-src/<lot>/`, pas le dossier servi. Au-delà d'environ 20 images, un lot par catégorie, chacun avec son slug, lancés en parallèle.
3. **Brief** dans `/tmp/<slug>-prompt.md`, en anglais, sur le modèle de [references/brief.md](references/brief.md). S'il existe des images de référence, demander à Codex de les regarder d'abord.
4. **Lancer** :
   ```bash
   mkdir -p <workdir>/<dossier>
   ~/.claude/skills/generate-asset/scripts/launch.sh <slug> <workdir> /tmp/<slug>-prompt.md
   ```
   Le script détache Codex (`setsid nohup`), écrit le PID dans `/tmp/<slug>.pid`, le log dans `/tmp/<slug>.log`, et affiche les lignes `model:` et `reasoning effort:` : vérifier `gpt-6-luna` et `high`.
5. **Attendre sans bloquer** : Bash en `run_in_background: true`, environ 1 minute par image ; un Monitor qui compte les fichiers du dossier suit la progression.
   ```bash
   while kill -0 $(cat /tmp/<slug>.pid) 2>/dev/null; do sleep 15; done; ls <workdir>/<dossier>; tail -20 /tmp/<slug>-last.md
   ```
6. **Contrôler** : `python3 ~/.claude/skills/generate-asset/scripts/contact_sheet.py <workdir>/<dossier> /tmp/<slug>-sheet.jpg`, lire la planche (cohérence, aucun texte, lisibilité en petit), ouvrir en grand les images douteuses. Pour refaire ou compléter : nouveau slug, brief restreint aux ids concernés (« generate the N MISSING/REJECTED illustrations (<ids>) — look at the existing files in <dossier> first and match their style exactly »).
7. **Intégrer** : `python3 ~/.claude/skills/generate-asset/scripts/to_webp.py <workdir>/<dossier> <dossier_servi> 768 80` recadre au carré, redimensionne et écrit `<id>.webp` en **écrasant** l'existant : ne remplacer des assets que si l'utilisateur l'a demandé. Adapter l'affichage si le format change (scène plein cadre : `object-fit: cover` en bandeau, pas une vignette `contain` avec ombre).

## Pièges Codex

- `--approve-for-me` est incompatible avec `-s/--sandbox` : seulement `-s workspace-write`.
- Un `codex exec` lancé sans `setsid` meurt au redémarrage de la session Claude : relancer alors seulement les ids manquants.
- Codex écrit d'abord dans `~/.codex/generated_images/<session>/` : y récupérer les images si la copie a échoué.
- `tmux: Operation not permitted` dans le log est sans conséquence.
- Transparence : la demander explicitement (`transparent background`) ; Codex préserve l'alpha de `image_gen`.
- Le skill système est dans `~/.codex/skills/.system/imagegen/`. Ne jamais passer en mode CLI/API (`~/.codex/skills/.system/imagegen/scripts/image_gen.py`, qui exige `OPENAI_API_KEY`) sans accord explicite.

## Références (à lire seulement si l'étape l'exige)

- [references/brief.md](references/brief.md) : questionnaire de direction artistique et modèle de brief Codex. À lire quand la DA du projet manque ou avant d'écrire le brief.
- `scripts/launch.sh` : lance Codex détaché ; commande sous-jacente `codex exec -m gpt-6-luna -c model_reasoning_effort=high -s workspace-write --skip-git-repo-check -C <workdir> -o /tmp/<slug>-last.md "<brief>"`.
- `scripts/contact_sheet.py` (planche contact), `scripts/to_webp.py` (conversion WebP) : usage en tête de fichier.
