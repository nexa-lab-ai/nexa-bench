# NEXA-Bench

A shared, mostly Turkish, multi-domain benchmark and assistant dataset built by NEXA Fellowship members.
Everyone adds their work through pull requests and keeps adding to their own files week by week.

| Domain | Contributor | Type |
|---|---|---|
| Turkish summarization and hallucination | Sedat | text |
| Counting and scene fidelity in image generation | Tuana | image |
| Character consistency in video models | Kaan | video |
| Electrical and electronics calculations | Mustafa | text |
| Exams from lecture notes | Kutay | text |

## Layout

Each person has **one file per folder**, named after their GitHub username. Keep adding to it; don't create new files each week.

```
questions/<username>.csv     benchmark questions          (Week 4)
chats/<username>.jsonl       assistant chats with tool calls (Week 5)
finetune/<username>.csv      one row per fine-tune run      (Week 5)
scripts/validate.py          format check, runs on every PR
```

Files starting with `_` are examples and are not counted. Copy them to start your own.

## questions/

| Column | Values |
|---|---|
| `id` | `abc-001` (lowercase, first 3 letters of your file name) |
| `type` | `text` · `image` · `video` |
| `domain`, `category` | free text; at least 3 categories per file |
| `difficulty` | `1` one step · `2` a few steps · `3` expert |
| `lang` | `tr` · `en` |
| `source` | `human` · `ai` (anything a model generated is `ai`) |
| `question`, `answer` | write the answer before testing any model |
| `scoring` | `exact_match` · `multiple_choice` · `numeric` · `checklist` · `rubric` |
| `tolerance` | required for `numeric`: `2%` or `0.01` |
| `notes` | source, solution hint, caveats |

For image/video questions, `question` is the prompt and `answer` is a `;`-separated checklist.
Goal: **at least 50 human-written questions**, 3 categories, all 3 difficulty levels.

## chats/

One chat per line (JSONL), in the standard chat format with tool calls:

```json
{"messages": [{"role": "system", ...}, {"role": "user", ...},
              {"role": "assistant", "tool_calls": [{"type": "function", "function": {"name": "search_products", "arguments": {...}}}]},
              {"role": "tool", "name": "search_products", "content": "..."},
              {"role": "assistant", "content": "..."}],
 "tools": [...schemas...], "source": "human|ai", "review": "ok|fixed|-", "split": "train|test"}
```

- `source`: `human` if you wrote it, `ai` if a model generated it.
- `review`: for AI chats you read by hand, `ok` or `fixed`; `-` otherwise. Delete rejected chats.
- `split`: optional, defaults to `train`. Put ~10% of chats in `test`, preferably human ones.

Goal: 30+ human and 280+ total chats, 3+ tools, 40%+ of chats with a tool call, 20%+ of AI chats reviewed.
The validator checks that tools are defined, arguments match the schema, chats aren't duplicated and Turkish characters aren't broken.

## finetune/

One row per training run. Add a new row for every run, even the bad ones.
See [`finetune/_example.csv`](finetune/_example.csv) for the columns.

- `method`: `full` · `lora` · `qlora`; `r` and `lora_alpha` are required for LoRA.
- `bench_*`: your benchmark score (%), `format_err_*`: answers that failed the format (count).
- `tool_acc_*` / `arg_acc_ft`: correct tool / correct arguments on your test chats (%).
- Run base and fine-tuned models with the same prompt and settings. At least 2 model families.

## Rules

1. Only change your own files.
2. Public set here, private set in your own repo. Put at least 50 of your 100+ questions here and don't publish the rest (contamination). Scores are public.
3. No copied content from the internet. If you adapted something, cite it in `notes`.
4. A question must have one clear correct answer. If it's debatable, use `rubric`.
5. No personal data in chats.

How to contribute: [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT. See [LICENSE](LICENSE).
