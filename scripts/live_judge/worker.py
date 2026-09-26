"""A real process boundary around persistent LangGraph interrupt/resume."""
import json
import sys
from pathlib import Path

from boussla.workflow import WorkflowRunner
from scripts.live_judge.support import Case, attempt, environment, load_scenario


def main():
    sid, directory, action, proposal = sys.argv[1:]
    runtime = Path(directory)
    with environment(runtime, "offline", set(), {}) as settings:
        case = Case(load_scenario(sid), settings)
        runner = WorkflowRunner(case.service, settings.checkpoint_db_path, planner=None)
        try:
            if action == "analysis-start":
                view = runner.run_analysis(case.co, case.case_id, case.version)
                answers = {q.question_id: "Réponse synthétique, aucun changement de preuve." for q in view.questions}
                (runtime / "answers.json").write_text(json.dumps(answers), encoding="utf-8")
                result = {"interrupted": bool(view.questions)}
            elif action == "analysis-resume":
                result = attempt(lambda: runner.submit_answers(case.co, case.case_id,
                    json.loads((runtime / "answers.json").read_text(encoding="utf-8"))))
                result.pop("value", None)
            elif action == "decision-start":
                value = runner.open_decision(case.off, case.case_id, proposal, case.version)
                result = {"interrupted": value["awaiting_decision"]}
            else:
                result = attempt(lambda: runner.decide(case.off, case.case_id, proposal, True))
                result.pop("value", None)
            result["version"] = case.version
            print(json.dumps(result))
        finally:
            runner.close()


if __name__ == "__main__":
    main()
