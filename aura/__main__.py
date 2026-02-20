"""CLI entry point for Project-AURA."""

from __future__ import annotations

import argparse
import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from . import __version__
from .config import load_config
from .ecosystem import populate_world
from .stats import StatsTracker
from .world import World

console = Console()

BANNER = r"""
    ╔═══════════════════════════════════════════════════╗
    ║                                                   ║
    ║      █████╗ ██╗   ██╗██████╗  █████╗              ║
    ║     ██╔══██╗██║   ██║██╔══██╗██╔══██╗             ║
    ║     ███████║██║   ██║██████╔╝███████║             ║
    ║     ██╔══██║██║   ██║██╔══██╗██╔══██║             ║
    ║     ██║  ██║╚██████╔╝██║  ██║██║  ██║             ║
    ║     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝             ║
    ║                                                   ║
    ║   Agents United in Responsive Atmospheres         ║
    ║   AI Multi-Agent Ecosystem Simulation             ║
    ╚═══════════════════════════════════════════════════╝
"""


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="aura",
        description="Project-AURA: AI Multi-Agent Ecosystem Simulation",
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to YAML config file (default: configs/default.yaml)",
    )
    parser.add_argument(
        "--width", "-W",
        type=int,
        default=None,
        help="Override world width",
    )
    parser.add_argument(
        "--height", "-H",
        type=int,
        default=None,
        help="Override world height",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without the web visualization server",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=None,
        help="WebSocket server port (default: 8765)",
    )
    parser.add_argument(
        "--speed", "-s",
        type=float,
        default=None,
        help="Tick speed in seconds (0 = max speed)",
    )
    parser.add_argument(
        "--ticks", "-t",
        type=int,
        default=0,
        help="Max ticks to run (0 = infinite)",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"Project-AURA v{__version__}",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Show banner
    console.print(BANNER, style="bold cyan")

    # Load config
    config = load_config(args.config)

    # Apply CLI overrides with validation
    if args.width:
        if args.width < 10 or args.width > 500:
            console.print("[bold red]Error:[/bold red] Width must be between 10 and 500.")
            sys.exit(1)
        config.world.width = args.width
    if args.height:
        if args.height < 10 or args.height > 500:
            console.print("[bold red]Error:[/bold red] Height must be between 10 and 500.")
            sys.exit(1)
        config.world.height = args.height
    if args.port:
        if args.port < 1024 or args.port > 65534:
            console.print("[bold red]Error:[/bold red] Port must be between 1024 and 65534.")
            sys.exit(1)
        config.server.port = args.port
    if args.speed is not None:
        if args.speed < 0:
            console.print("[bold red]Error:[/bold red] Speed must be non-negative.")
            sys.exit(1)
        config.world.tick_speed = args.speed

    # Create world
    world = World(config)

    # Attach stats tracker
    stats = StatsTracker()
    world.stats = stats

    # Populate
    console.print("[bold green]🌱 Seeding ecosystem...[/bold green]")
    populate_world(world)

    entity_summary = (
        f"  🌿 Flora: {world.flora_count()}  |  "
        f"🐇 Herbivores: {config.fauna.initial_herbivores}  |  "
        f"🐺 Predators: {config.fauna.initial_predators}  |  "
        f"🦊 Omnivores: {config.fauna.initial_omnivores}"
    )
    console.print(Panel(
        entity_summary,
        title="[bold]World Initialized[/bold]",
        subtitle=f"{config.world.width}×{config.world.height} grid",
        border_style="green",
    ))

    if args.headless:
        # Run without visualization
        console.print("\n[yellow]Running in headless mode (no web dashboard)...[/yellow]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")
        world.run(max_ticks=args.ticks)
    else:
        # Run with WebSocket server
        from .server import run_simulation_with_server

        try:
            asyncio.run(
                run_simulation_with_server(
                    world,
                    host=config.server.host,
                    port=config.server.port,
                )
            )
        except KeyboardInterrupt:
            console.print("\n[bold yellow]⚡ Simulation stopped.[/bold yellow]")

    # Final stats
    if stats.ticks_recorded > 0:
        console.print("\n")
        console.print(Panel(
            f"  Ticks: {stats.ticks_recorded}  |  "
            f"Births: {stats.total_births}  |  "
            f"Deaths: {stats.total_deaths}  |  "
            f"Peak Pop: {stats.peak_population}",
            title="[bold]Simulation Summary[/bold]",
            border_style="cyan",
        ))


if __name__ == "__main__":
    main()
