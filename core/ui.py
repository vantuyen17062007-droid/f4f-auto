"""
core/ui.py — Giao diện Console Hiện Đại Tích Hợp Thư Viện Rich
=============================================================
Cung cấp các thành phần giao diện chất lượng cao:
  - Banner chào đón bo viền gradient
  - Bảng tổng quan phiên làm việc (Session Overview)
  - Menu lựa chọn nền tảng & chế độ job
  - Bảng danh sách tài khoản liên kết
  - Khung báo cáo tổng kết phiên (Session Report)
  - Huy hiệu (Badges) hiển thị tiến trình job
  - Cơ chế dự phòng (Fallback) tự động nếu môi trường chưa cài rich
"""

import sys
from typing import Dict, Any, List

# Đảm bảo UTF-8 trên Windows console
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Thử nạp thư viện rich
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.align import Align
    from rich import box
    HAS_RICH = True
    console = Console(force_terminal=True, legacy_windows=False)
except ImportError:
    HAS_RICH = False
    console = None

from core.helpers import CYAN, GREEN, YELLOW, RED, WHITE, RESET, BOLD, DIM


def print_banner():
    """Hiển thị màn hình chào mừng thương hiệu Follow4Follow."""
    if HAS_RICH and console:
        banner_text = Text()
        banner_text.append("FOLLOW4FOLLOW  /  AUTO RUNNER\n", style="bold white")
        banner_text.append("◆  MULTI-PLATFORM AUTOMATION TOOL  ◆\n", style="bold green")
        banner_text.append("TikTok  •  Instagram  •  PC  •  Android (Termux)\n", style="cyan")
        banner_text.append("Console Interface  •  Version 2.0", style="dim yellow")

        panel = Panel(
            Align.center(banner_text),
            box=box.ROUNDED,
            border_style="bold cyan",
            padding=(1, 4),
            expand=False,
        )
        console.print()
        console.print(Align.center(panel))
        console.print()
    else:
        width = 62
        print()
        print(f"{CYAN}╭{'─' * width}╮{RESET}")
        print(f"{CYAN}│{RESET}{WHITE}{'FOLLOW4FOLLOW  /  AUTO RUNNER':^{width}}{RESET}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}{GREEN}{'◆':>5}  {'MULTI-PLATFORM AUTOMATION TOOL':<53}{RESET}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}{'TikTok  •  Instagram  •  PC  •  Android / Termux':^{width}}{CYAN}│{RESET}")
        print(f"{CYAN}├{'─' * width}┤{RESET}")
        print(f"{CYAN}│{RESET}  {YELLOW}●{RESET}  {WHITE}Console interface{RESET}                         {CYAN}Version 2.0{RESET}  {CYAN}│{RESET}")
        print(f"{CYAN}╰{'─' * width}╯{RESET}")
        print()


def render_session_overview(cfg: Dict[str, Any]):
    """Hiển thị bảng tóm tắt cấu hình hiện tại trước khi bắt đầu."""
    user = cfg.get("f4f_user", "N/A")
    plat = cfg.get("platform", "tiktok").upper()
    job_mode = cfg.get("job_type", "all").upper() if plat == "TIKTOK" else "FOLLOW (+35 XU)"
    max_jobs = str(cfg.get("max_jobs_per_session", 50))
    delay_str = f"{cfg.get('delay_min', 8)}-{cfg.get('delay_max', 18)}s"

    every_n = cfg.get("human_behavior_every_n_jobs", 5)
    times = cfg.get("human_behavior_scroll_times", 2)
    hb_desc = f"Sau {every_n} jobs -> Lướt {times} video" if cfg.get("human_behavior", True) else "Tắt"

    if HAS_RICH and console:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold cyan", width=12)
        grid.add_column(style="white")

        grid.add_row("ACCOUNT", f"[bold green]{user}[/bold green]")
        grid.add_row("PLATFORM", f"[bold yellow]{plat}[/bold yellow]   [bold cyan]MODE[/bold cyan]  [bold white]{job_mode}[/bold white]")
        grid.add_row("JOB LIMIT", f"[bold yellow]{max_jobs} jobs[/bold yellow]   [bold cyan]DELAY[/bold cyan]  [bold white]{delay_str}[/bold white]")
        grid.add_row("ANTI-BAN", f"[italic yellow]{hb_desc}[/italic yellow]")

        panel = Panel(
            grid,
            title="[bold cyan]SESSION OVERVIEW[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            expand=False,
            padding=(0, 2),
        )
        console.print(panel)
    else:
        print(f"{CYAN}╭─ {WHITE}SESSION OVERVIEW{CYAN} ───────────────────────────────────────╮{RESET}")
        print(f"{CYAN}│{RESET}  {CYAN}ACCOUNT{RESET}    {GREEN}{user:<48}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {CYAN}PLATFORM{RESET}   {YELLOW}{plat:<16}{RESET}{CYAN}MODE{RESET}   {WHITE}{job_mode:<23}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {CYAN}JOB LIMIT{RESET}  {WHITE}{max_jobs:<8}{RESET}  {CYAN}DELAY{RESET}  {WHITE}{delay_str}{RESET}{' ' * 18}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {CYAN}BROWSE{RESET}     {YELLOW}{hb_desc:<48}{CYAN}│{RESET}")
        print(f"{CYAN}╰────────────────────────────────────────────────────────────╯{RESET}")


def render_platform_menu():
    """Hiển thị menu chọn nền tảng kiếm coin."""
    if HAS_RICH and console:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold yellow", width=6)
        grid.add_column(style="bold white", width=14)
        grid.add_column(style="dim cyan")

        grid.add_row("[1]", "TikTok", "Follow tài khoản + Like video tự động")
        grid.add_row("[2]", "Instagram", "Follow trang cá nhân (+35 xu/job)")

        panel = Panel(
            grid,
            title="[bold cyan]CHỌN NỀN TẢNG[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            expand=False,
            padding=(0, 2),
        )
        console.print()
        console.print(panel)
    else:
        print(f"\n{CYAN}╭─ {WHITE}CHỌN NỀN TẢNG{CYAN} ─────────────────────────────────────────╮{RESET}")
        print(f"{CYAN}│{RESET}  {YELLOW}[1]{RESET}  {WHITE}TikTok{RESET}      {CYAN}Follow tài khoản + Like video{RESET}             {CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {YELLOW}[2]{RESET}  {GREEN}Instagram{RESET}  {CYAN}Follow trang cá nhân (+35 xu){RESET}            {CYAN}│{RESET}")
        print(f"{CYAN}╰────────────────────────────────────────────────────────────╯{RESET}")


def render_job_type_menu():
    """Hiển thị menu chọn loại job TikTok."""
    if HAS_RICH and console:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold yellow", width=6)
        grid.add_column(style="bold white", width=16)
        grid.add_column(style="dim cyan")

        grid.add_row("[1]", "FOLLOW ONLY", "Chỉ làm job follow tài khoản")
        grid.add_row("[2]", "LIKE ONLY", "Chỉ làm job thả tim (like) video")
        grid.add_row("[3]", "MIXED MODE", "Kết hợp cả Follow và Like video")

        panel = Panel(
            grid,
            title="[bold cyan]CHẾ ĐỘ JOB TIKTOK[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            expand=False,
            padding=(0, 2),
        )
        console.print()
        console.print(panel)
    else:
        print(f"\n{CYAN}╭─ {WHITE}CHẾ ĐỘ JOB TIKTOK{CYAN} ──────────────────────────────────────╮{RESET}")
        print(f"{CYAN}│{RESET}  {YELLOW}[1]{RESET}  {WHITE}FOLLOW ONLY{RESET}   {CYAN}Chỉ follow tài khoản{RESET}                   {CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {YELLOW}[2]{RESET}  {WHITE}LIKE ONLY{RESET}     {CYAN}Chỉ like video{RESET}                         {CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {YELLOW}[3]{RESET}  {GREEN}MIXED MODE{RESET}    {CYAN}Kết hợp Follow + Like{RESET}                {CYAN}│{RESET}")
        print(f"{CYAN}╰────────────────────────────────────────────────────────────╯{RESET}")


def render_accounts_table(platform_name: str, accounts: List[Dict[str, Any]], default_idx: int = 1):
    """Hiển thị danh sách tài khoản mạng xã hội liên kết dạng bảng Rich."""
    if HAS_RICH and console:
        table = Table(
            box=box.ROUNDED,
            border_style="cyan",
            title=f"[bold cyan]TÀI KHOẢN {platform_name.upper()} ĐÃ LIÊN KẾT[/bold cyan]",
            padding=(0, 1),
        )
        table.add_column("#", style="bold yellow", justify="center")
        table.add_column("Tài khoản", style="bold white")
        table.add_column("ID F4F", style="cyan", justify="center")
        table.add_column("Trạng thái", style="white", justify="center")
        table.add_column("Ghi chú", style="bold green", justify="center")

        for idx, acc in enumerate(accounts, start=1):
            name = acc.get("username") or acc.get("name") or "N/A"
            acc_id = str(acc.get("id", ""))
            status = acc.get("status", "Hoạt động")
            status_style = "[green]Hoạt động[/green]" if status == "Hoạt động" else f"[yellow]{status}[/yellow]"
            note = "★ Mặc định" if idx == default_idx else ""
            table.add_row(f"{idx:02}", f"@{name}", acc_id, status_style, note)

        console.print()
        console.print(table)
    else:
        print(f"\n{CYAN}╭─ {WHITE}TÀI KHOẢN {platform_name.upper()} ĐÃ LIÊN KẾT{CYAN} ───────────────────────────╮{RESET}")
        for idx, acc in enumerate(accounts, start=1):
            status = acc.get("status", "Hoạt động")
            name = acc.get("username") or acc.get("name") or "N/A"
            acc_id = acc.get("id", "")
            is_def = f" {GREEN}(Mặc định){RESET}" if idx == default_idx else ""
            print(f"{CYAN}│{RESET}  {YELLOW}[{idx:02}]{RESET}  {WHITE}@{name:<24}{RESET} {CYAN}ID:{RESET} {acc_id:<8} {CYAN}•{RESET} {status:<12}{is_def} {CYAN}│{RESET}")
        print(f"{CYAN}╰────────────────────────────────────────────────────────────────╯{RESET}")


def render_summary_report(platform_name: str, stats: Dict[str, Any], log_file: str):
    """Hiển thị bảng báo cáo kết quả phiên chạy (Session Report)."""
    s = stats
    total = s["followed"] + s["liked"] + s["already"] + s["skipped"] + s["errors"]

    if HAS_RICH and console:
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("Trạng thái", style="white", width=26)
        table.add_column("Số lượng", justify="right", style="bold", width=12)

        table.add_row("[bold green]✓ Follow thành công[/bold green]", f"[bold green]{s['followed']}[/bold green]")
        table.add_row("[bold magenta]♥ Like thành công[/bold magenta]", f"[bold magenta]{s['liked']}[/bold magenta]")
        table.add_row("[yellow]● Đã thực hiện trước[/yellow]", f"[yellow]{s['already']}[/yellow]")
        table.add_row("[dim yellow]↷ Đã bỏ qua[/dim yellow]", f"[dim yellow]{s['skipped']}[/dim yellow]")
        table.add_row("[bold red]! Lỗi[/bold red]", f"[bold red]{s['errors']}[/bold red]")
        table.add_section()
        table.add_row("[bold white]Tổng job xử lý[/bold white]", f"[bold white]{total}[/bold white]")
        table.add_row("[bold green]Coin nhận được[/bold green]", f"[bold green]~{s['coins_earned']} xu[/bold green]")

        panel = Panel(
            table,
            title=f"[bold cyan]SESSION REPORT ({platform_name.upper()})[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            expand=False,
            padding=(0, 1),
        )
        console.print()
        console.print(panel)
        console.print(f"[dim]File log chi tiết: {log_file}[/dim]\n")
    else:
        plat_tag = f"SESSION REPORT ({platform_name.upper()})"
        print(f"\n{CYAN}╭─ {WHITE}{plat_tag:<32}{CYAN} ─────────────────────╮{RESET}")
        print(f"{CYAN}│{RESET}  {GREEN}✓{RESET} Follow thành công   {GREEN}{s['followed']:>7}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {GREEN}♥{RESET} Like thành công     {GREEN}{s['liked']:>7}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {YELLOW}●{RESET} Đã thực hiện trước  {YELLOW}{s['already']:>7}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {YELLOW}↷{RESET} Đã bỏ qua           {YELLOW}{s['skipped']:>7}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  {RED}!{RESET} Lỗi                 {RED}{s['errors']:>7}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}├────────────────────────────────────────────────────────────┤{RESET}")
        print(f"{CYAN}│{RESET}  Tổng job xử lý       {WHITE}{total:>7}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}  Coin nhận được       {GREEN}~{s['coins_earned']:>6}{RESET}{' ' * 28}{CYAN}│{RESET}")
        print(f"{CYAN}╰────────────────────────────────────────────────────────────╯{RESET}\n")
        print(f"File log chi tiết: {log_file}")
