# Branch-start pack validation — V4-GIT-1

**Date:** 25 September 2026. This update changes development instructions, not the implemented BOUSSLA application.

## Actually checked during this update

All five updated handoffs were inspected programmatically for their assigned branch, atomic-commit requirement, explicit branch-only push command, staged-diff check and blocked-push reporting. The original V4 task text after each title is retained verbatim below the new instructions.

The final product lock, contract specification, architecture/data/scoring/source documents, all original synthetic fixtures, all sample PDF bytes, and all reference/application-scaffold Python files were compared with the supplied ZIP and remain byte-identical. The shared `AGENTS.md` has an explicit narrow amendment allowing Gemini to publish independent tests/reports; it does not give the reviewer ownership of production code.

The original reference suite was rerun:

```bash
python -m unittest discover -s reference -p 'test_*.py' -v
```

**30 reference tests passed.** Output is saved in `validation/reference_tests_branch_update.txt`. These are the small reference-function tests, not an application integration test or a real-world fraud benchmark.

Local Markdown links and fenced-block pairing were checked. The updated manifest was regenerated and the output ZIP was reopened to verify every archived file against the working copy. See `MANIFEST.json` for per-file hashes; the manifest intentionally does not hash itself.

## Not performed

No team Git repository, remote, branch or account was accessed. No team commits, Git pushes, pull requests or merges were executed. The Git command examples are instructions for the team's actual environment, not evidence that a remote was configured here. Account permissions, shell differences and repository protection rules still need to be checked locally.

No live Jev/LLM/Qdrant/LangGraph/LangSmith/provider integration was run. No new PDF content, legal corpus, trained model or finished UI was generated for this update. Original fixture validation/visual-inspection records are preserved from the earlier pack; this update did not rerender the unchanged PDFs.

## Packaging and scope

The package includes all original supporting files so each branch prompt can resolve its shared contracts and fixtures. Use the updated handoff on each assigned branch. Do not run earlier BOUSSLA versions as competing implementation instructions, and do not overwrite functioning code when copying this pack into an existing repository.
