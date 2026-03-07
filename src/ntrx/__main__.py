#!/usr/bin/env python
import typer

class NtrxCLI:
    def __init__(self):
        self.app = typer.Typer(help="ntrx CLI – Precision Streaming Infrastructure")

        # register subcommands
        self.app.command("ntripcaster")(self.run_ntripcaster)
        self.app.command("api")(self.run_api)

        # callback for default behavior
        @self.app.callback(invoke_without_command=True)
        def main_callback(ctx: typer.Context):
            if ctx.invoked_subcommand is None:
                typer.echo("Welcome to ntrx CLI 🛰️\n")
                typer.echo("Because of the `project.scripts` block in `pyproject.toml`,")
                typer.echo("installing this package (e.g., `pip install -e .`) automatically")
                typer.echo("creates a bin/exe wrapper called `ntrx`. So you can just type:\n")
                typer.echo("  • ntrx COMMAND             # via pip/setuptools entry point")
                typer.echo("  • python -m ntrx COMMAND   # as a python module\n")
                typer.echo("Available commands:")
                typer.echo("  • ntrx ntripcaster     → run NTRIP caster server")
                typer.echo("  • ntrx api       → run FastAPI WebSocket API")
                typer.echo("\nUse --help for more options.")
                raise typer.Exit()

    def run_ntripcaster(self):
        from ntrx.ntripcaster.ntripcaster_runner import NtripRunner
        NtripRunner().run()

    def run_api(self):
        from ntrx.fastapi_server import FastAPIServer
        FastAPIServer().run()

    def run(self):
        self.app()


def main():
    cli = NtrxCLI()
    cli.run()

if __name__ == "__main__":
    main()

app = NtrxCLI().app
