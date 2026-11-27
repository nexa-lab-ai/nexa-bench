# Contributing

You are a member of the organization, so no fork is needed: clone, work on your own branch, open a PR.

## 1. Clone (once)

```bash
git clone https://github.com/nexa-lab-ai/nexa-bench.git
cd nexa-bench
```

## 2. New branch for each PR

```bash
git switch main
git pull                              # get everyone's merged work
git switch -c alice/chats-first-30    # <name>/<what-you-add>
```

## 3. Edit your file and validate

Start from the example (once), then keep adding to the same file:

```bash
cp questions/_example.csv questions/<your-username>.csv   # or chats/_example.jsonl, finetune/_example.csv
python scripts/validate.py chats/<your-username>.jsonl
```

Don't push until you see `OK: no format errors.` Lines starting with `!` are warnings; fix them before your final submission.

## 4. Small commits

```bash
git add chats/<your-username>.jsonl
git commit -m "Add 30 hand-written sales assistant chats"
git push -u origin alice/chats-first-30
```

Say what you added. Messages like `update`, `fix` or `asdf` are not OK.

## 5. Open the PR

Click **Compare & pull request** on GitHub and fill in the checklist.
You can open it as a **Draft** to get early feedback.

## 6. Review

- Review the PR you are assigned to **yourself**: solve at least 5 questions or read at least 5 chats. Asking an AI to do it is not a review.
- Leave comments on lines (**Files changed** → **+** next to the line number). Be specific: "This question has two correct answers: …".
- Fix comments on your PR with new commits on the same branch, then **Resolve conversation**.
- Finish your review with **Approve**. Only the mentor merges; never merge your own PR.

## 7. Conflicts

```bash
git switch main && git pull
git switch alice/chats-first-30
git merge main
# fix the file, then:
git add . && git commit && git push
```

Since everyone works in their own files, conflicts are rare.
