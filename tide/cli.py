"""The `tide` command-line tool. More commands (prices, plan, destroy-all) arrive later."""

import typer

from tide import __version__, db

app = typer.Typer(help="Tide: multi-cloud spot arbitrage scheduler.", no_args_is_help=True)


@app.command()
def version() -> None:
    """Print the Tide version."""
    typer.echo(__version__)


@app.command("db-check")
def db_check() -> None:
    """Check that Tide can reach Postgres."""
    if db.check_connection():
        typer.echo("database: ok")
    else:
        typer.echo("database: unreachable (is `docker compose up -d db` running?)", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
