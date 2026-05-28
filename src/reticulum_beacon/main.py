"""CLI entry point for Reticulum Beacon."""

import typer

from .cli import commands

app = typer.Typer(
    name="beacon",
    help="🔴 Reticulum Beacon — Personal Reticulum transport node and service hub",
    no_args_is_help=True,
    add_completion=False,
)

app.command("setup")(commands.setup)
app.command("start")(commands.start)
app.command("stop")(commands.stop)
app.command("status")(commands.status)
app.command("config")(commands.config)
app.command("install")(commands.install)
app.command("uninstall")(commands.uninstall)
app.command("version")(commands.version)

# Sub-command groups
app.add_typer(commands.propagation_app, name="propagation")
app.add_typer(commands.identity_app, name="identity")
app.add_typer(commands.api_app, name="api")
app.add_typer(commands.bot_app, name="bot")


def main():
    app()


if __name__ == "__main__":
    main()
