# Status

- Project scaffolded: FastAPI app, Pydantic models, prompt builder,
  embeddings-based similarity check, real (non-invented) open-rate stats.
- 7 unit tests passing (stats, cosine similarity, prompt construction).
  No OpenAI API key was used yet — tests cover deterministic logic only.
- Not yet tested end-to-end with a real OpenAI API key.
- Not yet pushed to GitHub. No LICENSE added yet.

# Next steps

- [ ] Run a real end-to-end request with an OpenAI key, sanity-check output quality
- [ ] Decide on LICENSE (MIT used for the other public repo, aws-whisper)
- [ ] Push to GitHub
- [ ] Consider adding a simple example client script (curl or Python) to the README
