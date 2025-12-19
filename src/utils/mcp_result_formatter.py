"""
MCP Result Formatter
Handles special formatting and interpretation for MCP tool results.
"""

import json
from rich.console import Console


def format_ddpm_comparison_result(result_data: dict, coder_client, console: Console, verbose: bool = False) -> None:
    """
    Format and display DDPM code comparison results with LLM interpretation.
    
    Args:
        result_data: The parsed JSON result from compare_codes_with_ddpm tool
        coder_client: The LLM client for generating interpretation
        console: Rich console for output
        verbose: Whether to show detailed JSON output
    """
    # Extract key information
    similarity_pct = result_data.get('similarity_percentage', 0)
    interpretation = result_data.get('interpretation', 'N/A')
    metric = result_data.get('metric', 'cosine')
    file1 = result_data.get('file1', 'file1')
    file2 = result_data.get('file2', 'file2')
    
    # Display summary
    console.print(f"[bold cyan]Code Similarity Analysis:[/bold cyan]")
    console.print(f"  Files: [yellow]{file1}[/yellow] vs [yellow]{file2}[/yellow]")
    console.print(f"  Similarity: [bold green]{similarity_pct:.2f}%[/bold green]")
    console.print(f"  Interpretation: [bold]{interpretation}[/bold]")
    console.print(f"  Metric: {metric}\n")
    
    # Generate LLM interpretation
    if hasattr(coder_client, 'chat'):
        # Add context about how percentages are calculated
        metric_context = {
            'cosine': 'Raw cosine similarity of 0.905 is normalized: 1.0→100%, 0.85→50%, 0.5→0%',
            'euclidean': 'Raw euclidean distance is normalized: 0→100%, 10→50%, 40+→0%',
            'wasserstein': 'Raw wasserstein distance is normalized: 0→100%, 0.01→50%, 0.04+→0%',
            'mahalanobis': 'Raw mahalanobis distance is normalized: 0→100%, 5→50%, 15+→0%'
        }
        
        interpret_prompt = f"""Analyze this code similarity comparison result and provide a brief, practical interpretation:

Result:
- Files compared: {file1} vs {file2}
- Similarity: {similarity_pct:.2f}%
- Interpretation: {interpretation}
- Metric: {metric}
- File sizes: {result_data.get('file1_size', 0)} bytes vs {result_data.get('file2_size', 0)} bytes

Context about similarity calculation:
{metric_context.get(metric, '')}
The percentage normalization maps raw metric scores to a 0-100% scale where higher percentages indicate greater similarity.

Provide a 2-3 sentence analysis explaining what this similarity score means in practical terms. Consider file size differences if relevant."""

        console.print("[bold]LLM Interpretation:[/bold]")
        try:
            response = coder_client.chat(
                messages=[{"role": "user", "content": interpret_prompt}],
                stream=False,
                temperature=0.3
            )
            interpretation_text = response.get('message', {}).get('content', 'Unable to generate interpretation')
            console.print(interpretation_text)
        except Exception as e:
            console.print(f"[dim]Unable to generate LLM interpretation: {e}[/dim]")
        console.print()
    
    # Show full JSON only in verbose mode
    if verbose:
        console.print("[dim][bold]Detailed Result:[/bold][/dim]")
        console.print(json.dumps(result_data, indent=2))


def format_mcp_result(tool_name: str, result: str, coder_client, console: Console, verbose: bool = False) -> None:
    """
    Format and display MCP tool results with special handling for certain tools.
    
    Args:
        tool_name: Name of the MCP tool that was executed
        result: Raw result string from the tool
        coder_client: The LLM client for generating interpretation
        console: Rich console for output
        verbose: Whether to show detailed output
    """
    try:
        result_data = json.loads(result)
        
        # Special handling for compare_codes_with_ddpm
        if tool_name == 'compare_codes_with_ddpm' and result_data.get('status') == 'success':
            format_ddpm_comparison_result(result_data, coder_client, console, verbose)
        else:
            # Default behavior for other tools
            console.print("[bold]Result:[/bold]")
            console.print(json.dumps(result_data, indent=2))
            
    except (json.JSONDecodeError, ValueError, TypeError):
        # Not JSON, display as-is
        console.print("[bold]Result:[/bold]")
        console.print(result)
