# Privacy

Career OS is designed so that reusable logic and private candidate data never live in the same place.

## What is in this repository

- Engine code, JSON Schemas, scoring weights, routing rules and public Singapore policy references.
- Agent skills that contain operating instructions only.
- **Synthetic** fixtures: `candidate_profile.json`, `candidate_strategy.json`, and test jobs use invented people and companies (for example "Alex Example", "Synthetic Bank Alpha").

## What is deliberately excluded

Real profiles, resumes, cover letters, experience and project records, application trackers, discovery runs, job-specific application trails, interview or outcome records, contact details, identity or work-pass information, account identifiers, local file paths and screenshots.

## Using it with your own data

1. Keep your profile, strategy, resumes and trackers in a private folder outside this repository (or under `private/`, which is git-ignored).
2. Pass them to the engine with `--profile` and `--strategy`.
3. Before publishing any fork, search content **and** metadata (file names, document properties, logs, history) for identifiers, and replace examples with synthetic values.
