#!/usr/bin/env python3
import click
import csv
import io
from datetime import datetime, date
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm

import db

console = Console()

CATEGORY_COLORS = {
    "Food": "green",
    "Transport": "blue",
    "Housing": "magenta",
    "Entertainment": "yellow",
    "Health": "red",
    "Shopping": "cyan",
    "Education": "bright_blue",
    "Utilities": "orange3",
    "Travel": "bright_cyan",
    "Other": "white",
}

DEFAULT_CATEGORIES = list(CATEGORY_COLORS.keys())


def category_color(category: str) -> str:
    return CATEGORY_COLORS.get(category, "bright_white")


def format_amount(amount: float) -> str:
    return f"${amount:,.2f}"


def current_month() -> str:
    return date.today().strftime("%Y-%m")


def parse_month(ctx, param, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        datetime.strptime(value, "%Y-%m")
        return value
    except ValueError:
        raise click.BadParameter("Month must be in YYYY-MM format (e.g. 2024-03)")


@click.group()
def cli():
    """
    \b
    💰  Expense Tracker
    Track your spending from the terminal.
    """
    db.init_db()


@cli.command("add")
@click.option("--amount", "-a", type=float, prompt="Amount ($)", help="Expense amount")
@click.option(
    "--category",
    "-c",
    prompt="Category",
    type=click.Choice(DEFAULT_CATEGORIES, case_sensitive=False),
    help="Expense category",
)
@click.option("--description", "-d", prompt="Description", help="Short description")
@click.option(
    "--date",
    "-D",
    default=lambda: date.today().isoformat(),
    help="Date in YYYY-MM-DD format (default: today)",
)
def add_expense(amount: float, category: str, description: str, date: str):
    """Add a new expense."""
    if amount <= 0:
        console.print("[red]Amount must be greater than zero.[/red]")
        raise SystemExit(1)

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        console.print("[red]Date must be in YYYY-MM-DD format (e.g. 2024-03-15)[/red]")
        raise SystemExit(1)

    expense_id = db.add_expense(amount, category, description, date)

    panel = Panel(
        f"[bold green]Expense added![/bold green]\n\n"
        f"  [dim]ID:[/dim]          #{expense_id}\n"
        f"  [dim]Amount:[/dim]      [bold]{format_amount(amount)}[/bold]\n"
        f"  [dim]Category:[/dim]    [{category_color(category.title())}]{category.title()}[/{category_color(category.title())}]\n"
        f"  [dim]Description:[/dim] {description}\n"
        f"  [dim]Date:[/dim]        {date}",
        border_style="green",
        padding=(0, 1),
    )
    console.print(panel)


@cli.command("list")
@click.option("--category", "-c", default=None, help="Filter by category")
@click.option(
    "--month",
    "-m",
    default=None,
    callback=parse_month,
    help="Filter by month (YYYY-MM). Defaults to current month",
)
@click.option("--all", "show_all", is_flag=True, help="Show all months")
@click.option("--limit", "-n", default=None, type=int, help="Limit number of results")
def list_expenses(category: Optional[str], month: Optional[str], show_all: bool, limit: Optional[int]):
    """List expenses."""
    if not show_all and month is None:
        month = current_month()

    expenses = db.list_expenses(category=category, month=month, limit=limit)

    if not expenses:
        msg = "No expenses found"
        if category:
            msg += f" in [bold]{category}[/bold]"
        if month:
            msg += f" for [bold]{month}[/bold]"
        console.print(f"\n[dim]{msg}.[/dim]\n")
        return

    title = "Expenses"
    if month:
        title += f" — {month}"
    if category:
        title += f" / {category.title()}"

    table = Table(
        title=title,
        box=box.ROUNDED,
        show_header=True,
        header_style="bold",
        title_style="bold",
        padding=(0, 1),
    )
    table.add_column("ID", style="dim", justify="right", width=5)
    table.add_column("Date", width=12)
    table.add_column("Category", width=16)
    table.add_column("Description")
    table.add_column("Amount", justify="right", style="bold green")

    total = 0.0
    for row in expenses:
        color = category_color(row["category"])
        table.add_row(
            str(row["id"]),
            row["date"],
            f"[{color}]{row['category']}[/{color}]",
            row["description"],
            format_amount(row["amount"]),
        )
        total += row["amount"]

    console.print()
    console.print(table)
    console.print(
        f"  [dim]Total:[/dim] [bold green]{format_amount(total)}[/bold green]"
        + (f"  [dim]({len(expenses)} items)[/dim]" if len(expenses) > 1 else ""),
    )
    console.print()


@cli.command("summary")
@click.option(
    "--month",
    "-m",
    default=None,
    callback=parse_month,
    help="Month to summarize (YYYY-MM). Defaults to current month",
)
@click.option("--all", "show_all", is_flag=True, help="Summarize all time")
def summary(month: Optional[str], show_all: bool):
    """Show spending summary by category."""
    if not show_all and month is None:
        month = current_month()

    rows = db.get_summary(month=month)
    total = db.get_total(month=month)

    title = "Summary"
    if month:
        title += f" — {month}"
    else:
        title += " — All Time"

    if not rows:
        console.print(f"\n[dim]No expenses found for {month or 'all time'}.[/dim]\n")
        return

    table = Table(
        title=title,
        box=box.ROUNDED,
        show_header=True,
        header_style="bold",
        title_style="bold",
        padding=(0, 1),
    )
    table.add_column("Category", width=18)
    table.add_column("Items", justify="right", width=8)
    table.add_column("Total", justify="right", style="bold")
    table.add_column("Share", justify="right", width=10)
    table.add_column("Bar", width=24)

    max_val = max(r["total"] for r in rows) if rows else 1

    for row in rows:
        color = category_color(row["category"])
        pct = (row["total"] / total * 100) if total > 0 else 0
        bar_len = int((row["total"] / max_val) * 20)
        bar = f"[{color}]{'█' * bar_len}[/{color}][dim]{'░' * (20 - bar_len)}[/dim]"

        table.add_row(
            f"[{color}]{row['category']}[/{color}]",
            str(row["count"]),
            f"[{color}]{format_amount(row['total'])}[/{color}]",
            f"{pct:.1f}%",
            bar,
        )

    console.print()
    console.print(table)
    console.print(
        f"  [dim]Grand total:[/dim] [bold green]{format_amount(total)}[/bold green]"
        + f"  [dim]across {sum(r['count'] for r in rows)} expenses[/dim]"
    )
    console.print()


@cli.command("delete")
@click.argument("expense_id", type=int)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def delete_expense(expense_id: int, yes: bool):
    """Delete an expense by ID."""
    expense = db.get_expense(expense_id)
    if not expense:
        console.print(f"[red]No expense found with ID #{expense_id}.[/red]")
        raise SystemExit(1)

    console.print(
        f"\n  [dim]#{expense_id}[/dim]  [bold]{format_amount(expense['amount'])}[/bold]"
        f"  [{category_color(expense['category'])}]{expense['category']}[/{category_color(expense['category'])}]"
        f"  {expense['description']}  [dim]{expense['date']}[/dim]\n"
    )

    if not yes:
        confirmed = Confirm.ask("  Delete this expense?", default=False)
        if not confirmed:
            console.print("[dim]Cancelled.[/dim]")
            return

    db.delete_expense(expense_id)
    console.print(f"[green]Expense #{expense_id} deleted.[/green]\n")


@cli.command("categories")
def list_categories():
    """List all categories used in your expenses."""
    used = db.list_categories()

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Color")
    table.add_column("Category")
    table.add_column("Status", style="dim")

    for cat in DEFAULT_CATEGORIES:
        color = category_color(cat)
        in_use = cat in used
        table.add_row(
            f"[{color}]██[/{color}]",
            f"[bold]{cat}[/bold]",
            "in use" if in_use else "",
        )

    console.print()
    console.print(table)
    console.print()


@cli.command("export")
@click.option(
    "--month",
    "-m",
    default=None,
    callback=parse_month,
    help="Export specific month (YYYY-MM)",
)
@click.option("--output", "-o", default=None, help="Output file path (default: stdout)")
def export(month: Optional[str], output: Optional[str]):
    """Export expenses to CSV."""
    expenses = db.list_expenses(month=month)

    if not expenses:
        console.print("[dim]No expenses to export.[/dim]")
        return

    fieldnames = ["id", "date", "category", "description", "amount"]

    if output:
        with open(output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in expenses:
                writer.writerow({k: row[k] for k in fieldnames})
        console.print(f"[green]Exported {len(expenses)} expenses to [bold]{output}[/bold][/green]")
    else:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for row in expenses:
            writer.writerow({k: row[k] for k in fieldnames})
        click.echo(buf.getvalue(), nl=False)


if __name__ == "__main__":
    cli()
