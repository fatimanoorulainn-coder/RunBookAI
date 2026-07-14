from api.agent import run_investigation

investigation, traces = run_investigation(
    "why is ghost-service returning errors?"
)

print("===== FINAL RESULT =====")
print(investigation.model_dump_json(indent=2))
print(f"\n{len(traces)} steps taken")