# Building Jiyajale with Claude Code - Full Walkthrough

A step-by-step record of how we built a vocal separation tool for mom's YouTube singing channel, using Claude Code (Anthropic's AI coding assistant) on an M4 Mac. Every prompt below is exactly what I typed.

---

## Prompt 1: The Plan

I described the project to Claude — mom needs instrumental tracks from songs for her YouTube singing channel. I laid out the context (M4 Mac, Python 3.13, ffmpeg already installed) and what tools to use (yt-dlp for downloading, Demucs for AI vocal separation). Claude drafted a full implementation plan. I approved it.

---

## Prompt 2

> Implement the following plan:
> [pasted the full plan]

Claude went and did everything autonomously:

1. Created a Python virtual environment
2. Wrote `separate.sh` — a shell script that downloads a song and separates vocals from instrumentals
3. Installed all dependencies (`pip install -U yt-dlp demucs` — pulled in PyTorch, ~25 packages total)
4. Verified both tools work
5. Ran the first song: "Kisi Ranjish Ko Hawa Do Keh Main Zinda Hoon Abhi"
6. **Hit an error** — a missing `torchcodec` package. Claude caught it in the logs, installed the fix, and re-ran the separation without re-downloading
7. Done. Clean instrumental and isolated vocals saved as WAV files.

---

## Prompt 3

> open output/kisi-ranjish/stems/htdemucs_ft/original/no_vocals.wav

Claude opened the instrumental file in my audio player. The ghazal played back with vocals stripped out — just the instruments. Sounded clean.

---

## Prompt 4

> this has been super helpful and crazy. can you write a one pager the exact process of everything you/we did

Claude wrote `PROCESS.md` — a one-page doc covering what the tool does, the tech stack, setup, how it works, and key decisions.

---

## Prompt 5

> show me the one pager readable

Claude printed the full document in the terminal so I could read it right there.

---

## Prompt 6

> send an email to aupneja@gmail.com with this

Claude opened Apple Mail with the content pre-filled.

---

## Prompt 7

> try this again in gmail not mail app

Claude re-did it — opened a Gmail compose window in my browser with the recipient, subject, and body all filled in. Just had to hit send.

---

## Prompt 8

> can you put the prompts i used and your outputs in a nice readable document so i can walk my dad through what i did to accomplish this with u

Claude wrote this document.

---

## The End Result

8 prompts. ~15 minutes. Went from an empty folder to a working tool that turns any song into a karaoke track.

To process any new song, one command:

```
./separate.sh "Song Name or YouTube URL" "short-name"
```

Output:
```
output/short-name/
  original.wav              — the downloaded song
  stems/htdemucs_ft/original/
    no_vocals.wav           — instrumental (what mom sings over)
    vocals.wav              — isolated vocals (reference)
```

## What's Under the Hood

- **Claude Code** — Anthropic's AI coding assistant that ran in my terminal and did everything: wrote code, installed packages, debugged errors, sent emails
- **Demucs by Meta** — AI model that separates music into vocal and instrumental stems
- **yt-dlp** — Downloads audio from YouTube by name or URL
- **PyTorch on Apple Silicon** — Runs the AI model on the M4 GPU
