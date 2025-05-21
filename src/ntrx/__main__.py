#!/usr/bin/env python
import typer

class NtrxCLI:
    def __init__(self):
        self.app = typer.Typer(help="ntrx CLI – Precision Streaming Infrastructure")

        # register subcommands
        self.app.command("ntrip")(self.run_ntrip)
        self.app.command("api")(self.run_api)

        # callback for default behavior
        @self.app.callback(invoke_without_command=True)
        def main_callback(ctx: typer.Context):
            if ctx.invoked_subcommand is None:
                typer.echo("Welcome to ntrx CLI 🛰️\n")
                typer.echo("Available commands:")
                typer.echo("  • python -m ntrx ntrip     → run NTRIP caster server")
                typer.echo("  • python -m ntrx api       → run FastAPI WebSocket API")
                typer.echo("\nUse --help for more options.")
                raise typer.Exit()

    def run_ntrip(self):
        from ntrx.ntrip.ntrip_runner import NtripRunner
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
