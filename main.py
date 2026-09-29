import os
from dotenv import load_dotenv

def ui_loop():
    from rich.console import Console
    from rich.prompt import Prompt
    console = Console()
    
    console.print("[bold blue]Invoice Exception Resolution Agent[/bold blue]")
    
    while True:
        console.print("\n[bold]Select an action:[/bold]")
        console.print("1. Ingest Data (retain)")
        console.print("2. Detect Exceptions (recall)")
        console.print("3. Resolve Exceptions (Groq Loop)")
        console.print("4. Build Vendor Profiles (reflect)")
        console.print("5. Exit")
        
        choice = Prompt.ask("Choice", choices=["1", "2", "3", "4", "5"])
        
        if choice == "1":
            from hindsight.ingest import main as ingest_main
            ingest_main()
        elif choice == "2":
            from agents.exception_detector import main as detector_main
            detector_main()
        elif choice == "3":
            from agents.resolver import ExceptionResolver
            from data.synthetic.generator import SAMPLE_INVOICES
            from agents.exception_detector import detect_exceptions
            
            resolver = ExceptionResolver()
            console.print("[yellow]Running Resolution Pipeline...[/yellow]")
            
            for inv in SAMPLE_INVOICES:
                exceptions = detect_exceptions(inv)
                for exc in exceptions:
                    res = resolver.resolve(exc, inv)
                    console.print(f"Invoice: {inv.invoice_id} -> Action: {res.action.value} (Confidence: {res.confidence})")
        
        elif choice == "4":
            from hindsight.reflect_runner import generate_vendor_profiles
            generate_vendor_profiles()
            
        elif choice == "5":
            break

if __name__ == "__main__":
    load_dotenv()
    ui_loop()
