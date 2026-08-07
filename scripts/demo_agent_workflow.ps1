$ErrorActionPreference = "Stop"
$Python = if (Test-Path ".venv/Scripts/python.exe") { ".venv/Scripts/python.exe" } else { "python" }

Write-Host "OFFLINE DETERMINISTIC DEMO (not a real-model quality result)"
& $Python -m china_policy_rag.cli agent scope
& $Python -m china_policy_rag.cli agent run --question "What training-data duties apply in China?" --provider fake --show-tools
& $Python -m china_policy_rag.cli agent run --question "What copyright rules apply to EU GPAI training data?" --provider fake --show-tools
& $Python -m china_policy_rag.cli agent run --question "How do China and the EU differ in training-data transparency?" --provider fake --show-tools --trace-local
& $Python -m china_policy_rag.cli agent inspect --chunk-id "0d6d53f6-4019-5489-892f-573094e945fc"
& $Python -m china_policy_rag.cli agent run --question "What is the best GPU for model training?" --provider fake --show-tools
& $Python -m china_policy_rag.cli agent run --question "What exact training-data retention period applies?" --provider fake --show-tools
& $Python -m china_policy_rag.cli agent run --question "Compare China and EU training-data copyright requirements." --provider fake --output demo_agent_report.md --approve-export --overwrite
& $Python -m china_policy_rag.cli agent evaluate --cases data/evaluation/agent_workflows.yaml --provider fake --output reports/agent_evaluation.json

Write-Host "Start the optional local MCP server with:"
Write-Host "$Python -m china_policy_rag.cli mcp serve --transport stdio"
Write-Host "A real run requires .[openai], OPENAI_API_KEY, and --provider openai --model <model>."
