"""
diagnose.py
-----------
Utility to validate .env credentials before publishing to Instagram.

Usage:
    python execution/diagnose.py
"""

import os
import sys
from typing import Any

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv()
console = Console()

GRAPH_API = "https://graph.facebook.com/v21.0"


def graph_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """Run a Graph API GET request and return parsed JSON safely."""
    try:
        response = requests.get(f"{GRAPH_API}/{path}", params=params, timeout=15)
        response.raise_for_status()
    except requests.HTTPError:
        # Even on non-2xx, Graph API usually returns JSON with error details.
        try:
            return response.json()
        except ValueError:
            return {"error": {"message": response.text, "code": response.status_code}}
    except requests.RequestException as exc:
        return {"error": {"message": str(exc), "type": "RequestException"}}

    try:
        return response.json()
    except ValueError:
        return {"error": {"message": "Invalid JSON response from Graph API."}}


def check_env() -> bool:
    console.rule("[bold blue]1. Verificando variaveis de ambiente[/bold blue]")
    keys = ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_ACCOUNT_ID", "IMGBB_API_KEY", "GEMINI_API_KEY"]
    all_ok = True
    for key in keys:
        value = os.getenv(key, "")
        if not value or value.startswith("your_"):
            console.print(f"[red][ERRO] {key}: NAO configurado[/red]")
            all_ok = False
        else:
            masked = value[:6] + "..." + value[-6:]
            console.print(f"[green][OK] {key}: {masked}[/green]")
    return all_ok


def check_token() -> bool:
    console.rule("[bold blue]2. Validando Access Token com Graph API[/bold blue]")
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")

    if " " in token:
        console.print("[red][ERRO] Token contem espacos. Remova do .env.[/red]")
        return False
    if "\n" in token or "\r" in token:
        console.print("[red][ERRO] Token contem quebra de linha. Deve estar em uma unica linha.[/red]")
        return False
    if not token.startswith("EAA"):
        console.print("[yellow][WARN] Token nao comeca com 'EAA'.[/yellow]")
        console.print(f"[yellow]       Prefixo atual: '{token[:10]}'[/yellow]")

    data = graph_get(
        "debug_token",
        {
            "input_token": token,
            "access_token": token,  # Self-check for basic validation.
        },
    )

    if "error" in data:
        err = data["error"]
        console.print(f"[red][ERRO] Token invalido: {err.get('message')}[/red]")
        console.print(f"[red]       Tipo: {err.get('type')} | Codigo: {err.get('code')}[/red]")
        return False

    token_data = data.get("data", {})
    scopes = token_data.get("scopes", [])

    console.print("[green][OK] Token valido![/green]")
    console.print(f"  App ID: {token_data.get('app_id')}")
    console.print(f"  Tipo: {token_data.get('type')}")
    console.print(f"  Expira: {'Nunca' if not token_data.get('expires_at') else token_data.get('expires_at')}")
    console.print(f"  Permissoes: {', '.join(scopes)}")

    if "instagram_content_publish" not in scopes:
        console.print("[yellow][WARN] Permissao 'instagram_content_publish' nao encontrada no token.[/yellow]")
        console.print("[yellow]       Regenere o token com essa permissao no Graph API Explorer.[/yellow]")
    if "pages_show_list" not in scopes:
        console.print("[yellow][WARN] Permissao 'pages_show_list' nao encontrada no token.[/yellow]")
    if "pages_read_engagement" not in scopes:
        console.print("[yellow][WARN] Permissao 'pages_read_engagement' nao encontrada no token.[/yellow]")
    if ("pages_show_list" not in scopes) or ("pages_read_engagement" not in scopes):
        console.print(
            "[yellow]       Sem essas permissoes, pode ser impossivel descobrir a conta IG vinculada via /me/accounts.[/yellow]"
        )
    return True


def _find_linked_ig_accounts(token: str) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    """
    Discover IG Business/Creator accounts linked to pages visible by this token.
    Returns (accounts, error). Each account includes page_id/page_name + ig id/username.
    """
    data = graph_get(
        "me/accounts",
        {
            "fields": "id,name,instagram_business_account{id,username}",
            "limit": 100,
            "access_token": token,
        },
    )

    if "error" in data:
        return [], data["error"]

    discovered: list[dict[str, str]] = []
    for page in data.get("data", []):
        ig = page.get("instagram_business_account") or {}
        ig_id = ig.get("id")
        if not ig_id:
            continue
        discovered.append(
            {
                "page_id": str(page.get("id", "")),
                "page_name": str(page.get("name", "")),
                "ig_id": str(ig_id),
                "username": str(ig.get("username", "")),
            }
        )

    return discovered, None


def check_account() -> bool:
    console.rule("[bold blue]3. Validando Instagram Account ID[/bold blue]")
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    account_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "")

    # First try direct lookup (works when account_id is truly an IG account id).
    data = graph_get(
        account_id,
        {"fields": "id,username", "access_token": token},
    )
    if "error" not in data:
        console.print("[green][OK] Conta encontrada![/green]")
        console.print(f"  Username: @{data.get('username')}")
        console.print(f"  ID: {data.get('id')}")
        return True

    err = data["error"]
    err_message = err.get("message", "")
    console.print(f"[yellow][WARN] Falha na validacao direta do ID: {err_message}[/yellow]")

    linked_accounts, discovery_error = _find_linked_ig_accounts(token)
    if discovery_error:
        console.print(f"[red][ERRO] Nao foi possivel consultar contas vinculadas: {discovery_error.get('message')}[/red]")
        console.print("[yellow]       Verifique se o token inclui pages_show_list/pages_read_engagement.[/yellow]")
        return False

    if not linked_accounts:
        if "singular published story API is deprecated" in err_message:
            console.print("[red][ERRO] O INSTAGRAM_ACCOUNT_ID atual nao parece ser uma conta IG Business/Creator.[/red]")
            console.print("[yellow]       Esse erro costuma aparecer quando o ID eh de Story/Post/Pagina.[/yellow]")
        else:
            console.print("[red][ERRO] Nenhuma conta IG Business/Creator foi encontrada para este token.[/red]")
        return False

    for entry in linked_accounts:
        if account_id == entry["ig_id"]:
            console.print("[green][OK] Conta encontrada via paginas vinculadas![/green]")
            console.print(f"  Username: @{entry['username']}")
            console.print(f"  ID: {entry['ig_id']}")
            return True

        if account_id == entry["page_id"]:
            console.print("[red][ERRO] INSTAGRAM_ACCOUNT_ID esta com o Page ID, nao com o Instagram User ID.[/red]")
            console.print(f"[yellow]       Pagina: {entry['page_name']} ({entry['page_id']})[/yellow]")
            console.print(f"[yellow]       Use este valor no .env: INSTAGRAM_ACCOUNT_ID={entry['ig_id']}[/yellow]")
            return False

    console.print("[red][ERRO] INSTAGRAM_ACCOUNT_ID nao bate com nenhuma conta IG vinculada ao token.[/red]")
    console.print("[yellow]       Contas IG encontradas:[/yellow]")
    for entry in linked_accounts:
        console.print(
            f"[yellow]       - @{entry['username']} | IG ID: {entry['ig_id']} | Pagina: {entry['page_name']} ({entry['page_id']})[/yellow]"
        )
    return False


def main() -> None:
    console.print(Panel("[bold]Instagram Agent - Diagnostico de Credenciais[/bold]", style="blue"))

    env_ok = check_env()
    if not env_ok:
        console.print("\n[red]Configure o .env antes de continuar.[/red]")
        sys.exit(1)

    token_ok = check_token()
    if not token_ok:
        console.print(
            Panel(
                "[bold]Como gerar um token valido:[/bold]\n\n"
                "1. Acesse: https://developers.facebook.com/tools/explorer/\n"
                "2. Selecione seu App -> Generate Access Token\n"
                "3. Adicione as permissoes:\n"
                "   - instagram_content_publish\n"
                "   - instagram_basic\n"
                "   - pages_show_list\n"
                "   - pages_read_engagement\n"
                "4. Clique em Generate Access Token\n"
                "5. Cole em INSTAGRAM_ACCESS_TOKEN no .env\n\n"
                "[yellow]Nota: tokens do Graph API Explorer expiram rapido.\n"
                "Para producao, use Long-Lived Token (60 dias).[/yellow]",
                title="Guia de Token",
                border_style="yellow",
            )
        )
        sys.exit(1)

    account_ok = check_account()
    if not account_ok:
        console.print(
            Panel(
                "[bold]Como corrigir INSTAGRAM_ACCOUNT_ID:[/bold]\n\n"
                "1. Garanta que o valor no .env eh o Instagram User ID (Business/Creator), nao Page ID.\n"
                "2. Se tiver duvida, rode no Graph API Explorer:\n"
                "   GET /me/accounts?fields=id,name,instagram_business_account{id,username}\n"
                "3. Copie instagram_business_account.id para INSTAGRAM_ACCOUNT_ID.\n",
                title="Guia de Account ID",
                border_style="yellow",
            )
        )
        sys.exit(1)

    console.print("\n[bold green][OK] Diagnostico concluido. Pronto para publicar.[/bold green]")


if __name__ == "__main__":
    main()
