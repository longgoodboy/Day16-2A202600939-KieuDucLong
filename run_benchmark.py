from __future__ import annotations
import os
import json
import random
from pathlib import Path
import typer
from dotenv import load_dotenv
from rich import print
from rich.progress import track
from src.reflexion_lab.agents import ReActAgent, ReflexionAgent
from src.reflexion_lab.reporting import build_report, save_report
from src.reflexion_lab.utils import load_dataset, save_jsonl

load_dotenv()
app = typer.Typer(add_completion=False)

@app.command()
def main(
    dataset: str = typer.Option("data/my_test_set.json", help="Path to the dataset JSON"),
    out_dir: str = typer.Option("outputs/sample_run", help="Output directory"),
    reflexion_attempts: int = typer.Option(3, help="Max attempts for ReflexionAgent"),
    mode: str = typer.Option("mock", help="mock or llm"),
    model: str = typer.Option("gpt-4o-mini", help="LLM model name"),
    max_examples: int = typer.Option(0, help="Max examples to run (0 for all)"),
    seed: int = typer.Option(42, help="Random seed"),
    temperature: float = typer.Option(0.0, help="LLM temperature")
) -> None:
    # Set env vars for runtime
    os.environ["REFLEXION_MODE"] = mode
    os.environ["REFLEXION_MODEL"] = model
    os.environ["REFLEXION_TEMPERATURE"] = str(temperature)
    
    random.seed(seed)
    
    print(f"Loading dataset from {dataset}...")
    examples = load_dataset(dataset)
    
    if max_examples > 0:
        examples = examples[:max_examples]
        
    print(f"Loaded {len(examples)} examples.")
        
    react = ReActAgent()
    reflexion = ReflexionAgent(max_attempts=reflexion_attempts)
    
    react_records = []
    print("\nRunning ReActAgent...")
    for example in track(examples, description="ReAct"):
        try:
            react_records.append(react.run(example))
        except Exception as e:
            print(f"[red]Error on {example.qid}: {e}[/red]")
            
    reflexion_records = []
    print("\nRunning ReflexionAgent...")
    for example in track(examples, description="Reflexion"):
        try:
            reflexion_records.append(reflexion.run(example))
        except Exception as e:
            print(f"[red]Error on {example.qid}: {e}[/red]")
            
    all_records = react_records + reflexion_records
    out_path = Path(out_dir)
    save_jsonl(out_path / "react_runs.jsonl", react_records)
    save_jsonl(out_path / "reflexion_runs.jsonl", reflexion_records)
    
    report = build_report(all_records, dataset_name=Path(dataset).name, mode=mode)
    json_path, md_path = save_report(report, out_path)
    
    from rich.table import Table
    from rich.console import Console
    console = Console()
    
    s = report.summary
    react = s.get("react", {})
    reflexion = s.get("reflexion", {})
    delta = s.get("delta_reflexion_minus_react", {})
    
    # 1. Performance Table
    perf_table = Table(title="Agent Performance Comparison")
    perf_table.add_column("Metric", justify="left", style="cyan", no_wrap=True)
    perf_table.add_column("ReAct", justify="right", style="magenta")
    perf_table.add_column("Reflexion", justify="right", style="green")
    perf_table.add_column("Delta (+/-)", justify="right", style="yellow")
    
    perf_table.add_row(
        "Accuracy (Exact Match)", 
        f"{react.get('accuracy', 0)*100:.2f}%", 
        f"{reflexion.get('accuracy', 0)*100:.2f}%", 
        f"{delta.get('em_abs', 0)*100:+.2f}%"
    )
    perf_table.add_row(
        "Avg Attempts per Question", 
        f"{react.get('avg_attempts', 0):.2f}", 
        f"{reflexion.get('avg_attempts', 0):.2f}", 
        f"{delta.get('attempts_abs', 0):+.2f}"
    )
    
    # 2. Cost & Latency Table
    cost_table = Table(title="Cost and Latency Estimation")
    cost_table.add_column("Metric", justify="left", style="cyan", no_wrap=True)
    cost_table.add_column("ReAct", justify="right", style="magenta")
    cost_table.add_column("Reflexion", justify="right", style="green")
    cost_table.add_column("Delta (+/-)", justify="right", style="yellow")
    
    cost_table.add_row(
        "Avg Tokens per Question", 
        f"{react.get('avg_tokens', 0):.0f}", 
        f"{reflexion.get('avg_tokens', 0):.0f}", 
        f"{delta.get('tokens_abs', 0):+.0f}"
    )
    
    # Cost assumes ~$0.30 per 1M tokens combined
    react_cost = react.get('avg_tokens', 0) * 0.3 / 1000000
    ref_cost = reflexion.get('avg_tokens', 0) * 0.3 / 1000000
    delta_cost = ref_cost - react_cost
    
    cost_table.add_row(
        "Est. Cost per 1000 Qs", 
        f"${react_cost*1000:.4f}", 
        f"${ref_cost*1000:.4f}", 
        f"${delta_cost*1000:+.4f}"
    )
    
    cost_table.add_row(
        "Avg Latency (ms)", 
        f"{react.get('avg_latency_ms', 0):.0f} ms", 
        f"{reflexion.get('avg_latency_ms', 0):.0f} ms", 
        f"{delta.get('latency_abs', 0):+.0f} ms"
    )
    
    console.print()
    console.print(perf_table)
    console.print()
    console.print(cost_table)
    console.print()
    
    print(f"[green]OK. Report JSON Saved:[/green] {json_path}")
    print(f"[green]OK. Report MD Saved:[/green] {md_path}")

if __name__ == "__main__":
    app()
