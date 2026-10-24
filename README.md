# PolicyForge AI

An Operating Systems course project for comparing CPU scheduling algorithms and understanding why they pass or fail a requirement.

**Status: work in progress.** The current version is a complete, usable local prototype. It can run independently, and the main features work together. Further updates can improve the model, tutor and interface without being necessary to use the current build.

## What it does

- Simulates FCFS, SJF, Priority and Round Robin on the same set of processes.
- Checks goals such as “interactive jobs must start within 2 units”.
- Shows response, waiting and turnaround times, charts and a step-by-step execution timeline.
- Searches for a workload that breaks a scheduler's goal, reduces it and lets you replay the failure.
- Uses a trained decision tree to suggest a scheduler, then checks the prediction against simulation.
- Includes a separate tutor page with local explanations and worked calculations. Gemini or OpenAI can optionally generate additional explanations.

The website has three pages: **Scheduling Lab**, **AI Tutor** and **About**. This is a simulation; it does not control the computer's actual scheduler.

## Run locally

Use Python 3.10 or newer. There are no external Python packages to install.

```bash
python3 -B server.py --port 8767
```

Open http://127.0.0.1:8767/ and keep the Terminal running. Press Control + C to stop it. If the port is occupied, use another number with `--port`.

The simulator, advisor and local tutor work without an API key. For generative answers, set `GEMINI_API_KEY` or `OPENAI_API_KEY` in the server environment before starting it. Set `AI_PROVIDER=gemini` or `AI_PROVIDER=openai` to select a provider. `GEMINI_MODEL` and `OPENAI_MODEL` can override the default model. Keep keys out of source files and Git commits.

## The AI parts

The scheduler advisor is a small decision tree implemented in Python. Its dataset contains **240 synthetic workloads** labelled by the simulator: 192 for training and 48 for testing. It got **32/48 predictions correct (66.7%)**, compared with 56.3% for the majority-label baseline. This is a small educational experiment, not evidence of real-world scheduler performance. Priority has no winning labels in this dataset, which limits the model.

The local tutor uses **TF-IDF and cosine similarity** over example questions to retrieve lessons. It calculates numerical evidence using the simulator. Optional generative answers use an external model and may be incorrect; the measured results remain the reference.

## Code layout

| Location | Purpose |
| --- | --- |
| `server.py` | Local HTTP server and API routes |
| `policyforge/core.py` | Scheduling algorithms and metrics |
| `policyforge/experiments.py` | Goal checking, comparisons and failure search |
| `policyforge/advisor.py` | Decision-tree training functions and prediction |
| `policyforge/tutor.py` | Local lesson retrieval and worked examples |
| `policyforge/llm_tutor.py` | Optional Gemini/OpenAI connection |
| `scripts/train_advisor.py` | Generate the dataset, train and evaluate the tree |
| `data/` | Saved dataset and trained model |
| `web/` | Website pages, styles and JavaScript |
| `tests/` | Automated checks |
| `outputs/PolicyForge_AI_Review.pptx` | Review presentation from this development stage |

## Checks and retraining

```bash
python3 -B -m unittest discover -s tests -v
python3 -B scripts/train_advisor.py
```

Restart the server after retraining to reload the saved model.

## Scope and next steps

The simulation has one CPU, known bursts, finite workloads and no I/O blocking. SJF and Priority are non-preemptive. Job type selects which processes a goal checks; it does not change scheduling order. A passing workload is not a guarantee for every workload.

Possible updates include more balanced training data, evaluation across more splits, additional scheduling policies, I/O bursts and better tutor coverage. The included slides describe the review checkpoint; the source code is the current implementation.

## AI assistance

**Yes, I have taken assistance from AI while building this project.** AI tools helped with implementation, debugging, interface design, tests and documentation. This is an AI-assisted student project, and I am studying the implementation as part of the work. I am not presenting it as entirely unaided work or as a production operating-system scheduler.

Aarav Dangwal — 24BCE0711
