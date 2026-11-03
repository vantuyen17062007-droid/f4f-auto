"""
core/ui.py — Giao diện Console "Premium" cho Follow4Follow Auto Runner
=====================================================================
Ngôn ngữ thiết kế:
  - Banner gradient cyan → indigo → fuchsia (Rich) / ladder màu tương đương (fallback)
  - Các panel bo viền thống nhất, tiêu đề nhấn mạnh ở viền trên
  - Menu dạng danh sách có phụ đề gợi ý & chú thích decode ý nghĩa
  - Session Overview / PREFLIGHT / Summary có bullet icon + bar trực quan
  - Fallback thủ công (không cần rich) vẽ khung Unicode tự co giãn theo nội dung.

Export (API ổn định cho các module khác):
  print_banner, render_session_overview, render_platform_menu,
  render_job_type_menu, render_saved_config_menu, render_preflight,
  render_accounts_table, render_summary_report, HAS_RICH, console, box, Panel
"""

import sys
from typing import Dict, Any, List, Sequence, Tuple, Union

# Đảm bảo UTF-8 trên Windows console
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from core.helpers import (
    CYAN, GREEN, YELLOW, RED, WHITE, BOLD, DIM, RESET, strip_ansi,
)

# ── Thử nạp thư viện rich ────────────────────────────────────────────────
try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.align import Align
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    Console = Panel = Table = Text = Align = Group = box = None

console = Console() if HAS_RICH else None

# Bật tắt màu fallback (rỗng khi stdout là pipe/file — được helpers quyết định)
COLOR_ON = bool(GREEN)


# ════════════════════════════════════════════════════════════════════════
#  ENGINE MÀU GRADIENT
# ════════════════════════════════════════════════════════════════════════

# Rich: interpolate hex giữa các điểm mốc
_GRAD_HEX = ((0x22, 0xD3, 0xEE), (0x81, 0x8C, 0xF8), (0xE8, 0x79, 0xF9))
# Fallback: ladder ANSI chuẩn (cyan → blue → magenta)
_GRAD_ANSI = ("\033[96m", "\033[94m", "\033[95m")


def _hex_at(t: float) -> str:
    """Trả về mã màu hex theo vị trí tham số t ∈ [0, 1] trên gradient."""
    t = max(0.0, min(1.0, t))
    x = t * (len(_GRAD_HEX) - 1)
    i = min(int(x), len(_GRAD_HEX) - 2)
    f = x - i
    a, b = _GRAD_HEX[i], _GRAD_HEX[i + 1]
    return "#{:02x}{:02x}{:02x}".format(*(
        round(a[k] + (b[k] - a[k]) * f) for k in range(3)
    ))


def _grad_ansi(pos: int, total: int) -> str:
    """Trả về mã màu ANSI follower theo gradient cho vị trí trong dãy."""
    if not COLOR_ON or total <= 1:
        return ""
    idx = min(int(pos / (total - 1) * (len(_GRAD_ANSI) - 1)), len(_GRAD_ANSI) - 1)
    return _GRAD_ANSI[idx]


def _bar(count: int, total: int, width: int = 10) -> str:
    """Chuỗi bar ▰/▱ hiển thị tỉ lệ count/total với độ dài `width`."""
    filled = 0 if total <= 0 else round(width * min(count, total) / max(total, 1))
    return "▰" * int(filled) + "▱" * (width - int(filled))


# ════════════════════════════════════════════════════════════════════════
#  KHUNG FALLBACK (không rich) — tự co giãn theo nội dung
# ════════════════════════════════════════════════════════════════════════

def _frame(title: str, lines: Sequence[Union[str, None]], _color=CYAN) -> None:
    """Vẽ khung Unicode thủ công. Phần tử `None` trong `lines` vẽ đường phân cách '├────┤'."""
    contents = [l for l in lines if isinstance(l, str)]
    plain_max = max((len(strip_ansi(l)) for l in contents), default=0)
    inner = max(50, plain_max + 4, len(title) + 6)

    header_fill = max(3, inner - len(title) - 4)
    print(f"\n{_color}╭─{RESET}{BOLD}{WHITE} {title} {RESET}{_color}{'─' * header_fill}╮{RESET}")
    for line in lines:
        if line is None:
            print(f"{_color}├{'─' * inner}┤{RESET}")
            continue
        pad = " " * max(0, inner - 2 - len(strip_ansi(line)))
        print(f"{_color}│{RESET}  {line}{pad}{_color}│{RESET}")
    print(f"{_color}╰{'─' * inner}╯{RESET}")


# ════════════════════════════════════════════════════════════════════════
#  1. BANNER
# ════════════════════════════════════════════════════════════════════════

def print_banner():
    """Banner thương hiệu có gradient theo từng ký tự (Rich) / ladder màu (fallback)."""
    title = "FOLLOW4FOLLOW"

    if HAS_RICH and console:
        big = Text()
        for i, ch in enumerate(title):
            big.append(ch, style=f"bold {_hex_at(i / max(len(title) - 1, 1))}")
        sub = Text()
        sub.append("◆ ", style="bold yellow")
        sub.append("MULTI-PLATFORM AUTO RUNNER", style="bold white")
        sub.append(" ◆", style="bold yellow")
        chips = Text()
        chips.append("TikTok", style="bold cyan")
        chips.append("  ✦  ", style="dim")
        chips.append("Instagram", style="bold fuchsia")
        chips.append("  ✦  ", style="dim")
        chips.append("Android (Termux)", style="bold green")
        meta = Text()
        meta.append("Console UI v2.0", style="dim yellow")
        meta.append("  •  ", style="dim")
        meta.append("PC / Linux / Android", style="dim")

        body = Group(
            Align.center(big),
            Align.center(sub),
            Align.center(chips),
            Align.center(meta),
        )
        panel = Panel(
            body,
            box=box.DOUBLE,
            border_style="bold cyan",
            padding=(1, 4),
        )
        console.print()
        console.print(Align.center(panel))
        console.print()
    else:
        lines = [
            "".join(
                f"{_grad_ansi(i, len(title))}{BOLD}{ch}{RESET}"
                for i, ch in enumerate(title)
            ),
            f"{YELLOW}◆{RESET} {WHITE}MULTI-PLATFORM AUTO RUNNER{RESET} {YELLOW}◆{RESET}",
            (
                f"{CYAN}TikTok{RESET}  {DIM}✦  {RESET}"
                f"{YELLOW}Instagram{RESET}  {DIM}✦  {RESET}"
                f"{GREEN}Android (Termux){RESET}"
            ),
            f"{DIM}Console UI v2.0  •  PC / Linux / Android{RESET}",
        ]
        width = max(len(strip_ansi(l)) for l in lines) + 8

        print()
        print(f"{CYAN}╭{'─' * width}╮{RESET}")
        print(f"{CYAN}│{RESET}{' ' * width}{CYAN}│{RESET}")
        for line in lines:
            plain = len(strip_ansi(line))
            left = (width - plain) // 2
            right = width - plain - left
            print(f"{CYAN}│{RESET}{' ' * left}{line}{' ' * right}{CYAN}│{RESET}")
        print(f"{CYAN}│{RESET}{' ' * width}{CYAN}│{RESET}")
        print(f"{CYAN}╰{'─' * width}╯{RESET}")
        print()


# ════════════════════════════════════════════════════════════════════════
#  2. SESSION OVERVIEW
# ════════════════════════════════════════════════════════════════════════

def render_session_overview(cfg: Dict[str, Any]):
    """Bảng tóm tắt cấu hình phiên chạy hiển thị trước khi bắt đầu."""
    user = cfg.get("f4f_user", "N/A")
    plat = str(cfg.get("platform", "tiktok")).upper()
    job_mode = (
        str(cfg.get("job_type", "all")).upper() if plat == "TIKTOK" else "FOLLOW ONLY"
    )
    max_jobs = int(cfg.get("max_jobs_per_session", 50))
    delay_str = f"{cfg.get('delay_min', 8)} – {cfg.get('delay_max', 18)}s"

    every_n = cfg.get("human_behavior_every_n_jobs", 5)
    times = cfg.get("human_behavior_scroll_times", 2)
    hb_desc = (
        f"Kích hoạt ngẫu nhiên {every_n}±2 job → lướt {times}±1 video"
        if cfg.get("human_behavior", True) else "Đang tắt"
    )

    if HAS_RICH and console:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold cyan", justify="right", width=12)
        grid.add_column(style="white")

        grid.add_row("👤  ACCOUNT", f"[bold green]{user}[/bold green]")
        grid.add_row("📱  PLATFORM", f"[bold yellow]{plat}[/bold yellow]   [dim]│[/dim]   MODE [bold white]{job_mode}[/bold white]")
        grid.add_row("🎯  JOB LIMIT", f"[bold yellow]{max_jobs} jobs[/bold yellow]   [dim]│[/dim]   DELAY [bold white]{delay_str}[/bold white]")
        grid.add_row("🛡  ANTI-BAN", f"[italic yellow]{hb_desc}[/italic yellow]")

        panel = Panel(
            grid,
            title=f"[bold cyan]SESSION OVERVIEW[/bold cyan] [dim]— {plat}[/dim]",
            border_style="cyan",
            box=box.ROUNDED,
            expand=False,
            padding=(0, 2),
        )
        console.print(panel)
    else:
        lab_acct = f"{CYAN}ACCOUNT{RESET}"
        lab_plat = f"{CYAN}PLATFORM{RESET}"
        lab_job = f"{CYAN}JOB LIMIT{RESET}"
        lab_ab = f"{CYAN}ANTI-BAN{RESET}"
        rows = [
            f"{lab_acct}      {GREEN}{user}{RESET}",
            f"{lab_plat}     {YELLOW}{plat}{RESET}{DIM} │ {RESET}MODE {WHITE}{job_mode}{RESET}",
            f"{lab_job}  {YELLOW}{max_jobs} jobs{RESET}{DIM} │ {RESET}DELAY {WHITE}{delay_str}{RESET}",
            f"{lab_ab}     {YELLOW}{hb_desc}{RESET}",
            None,
            f"{DIM}Sẵn sàng! Về terminal để theo dõi stream job...{RESET}",
        ]
        _frame("SESSION OVERVIEW", rows)


# ════════════════════════════════════════════════════════════════════════
#  3. MENU — NỀN TẢNG / LOẠI JOB / CẤU HÌNH CŨ
# ════════════════════════════════════════════════════════════════════════

def _rich_menu(title: str, opts: Sequence[Tuple[str, str, str]]) -> None:
    """Render menu bằng Rich: opts = (key, name, desc)."""
    if not (HAS_RICH and console):
        return
    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="bold yellow", width=5)
    grid.add_column(style="bold white", width=17)
    grid.add_column(style="dim cyan")

    for key, name, desc in opts:
        grid.add_row(f"[{key}]", name, desc)

    console.print()
    console.print(
        Panel(
            grid,
            title=f"[bold cyan]{title}[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            expand=False,
            padding=(0, 2),
        )
    )


def render_platform_menu():
    """Hiển thị menu chọn nền tảng kiếm coin."""
    if HAS_RICH and console:
        _rich_menu("CHỌN NỀN TẢNG", [
            ("1", "TikTok",     "Follow +26 xu • Like +10 xu/video"),
            ("2", "Instagram",  "Follow trang cá nhân +35 xu/job"),
        ])
    else:
        k1, k2 = f"{YELLOW}[1]{RESET}", f"{YELLOW}[2]{RESET}"
        n1, n2 = f"{WHITE}TikTok{RESET}", f"{YELLOW}Instagram{RESET}"
        d1, d2 = f"{CYAN}Follow +26 xu • Like +10 xu/video{RESET}", \
                 f"{CYAN}Follow trang cá nhân +35 xu/job{RESET}"
        _frame("CHỌN NỀN TẢNG", [
            f"{k1}  {n1:<22} {d1}",
            f"{k2}  {n2:<22} {d2}",
        ])


def render_job_type_menu():
    """Hiển thị menu chọn loại job TikTok."""
    if HAS_RICH and console:
        _rich_menu("CHẾ ĐỘ JOB TIKTOK", [
            ("1", "FOLLOW ONLY",  "Chỉ làm job follow tài khoản"),
            ("2", "LIKE ONLY",    "Chỉ làm job thả tim (like) video"),
            ("3", "MIXED MODE",   "Kết hợp cả Follow và Like video"),
        ])
    else:
        k = [f"{YELLOW}[{c}]{RESET}" for c in "12"]
        k3 = f"{YELLOW}[3]{RESET}"
        rows = [
            f"{k[0]}  {WHITE}{'FOLLOW ONLY':<22}{RESET} {CYAN}Chỉ làm job follow tài khoản{RESET}",
            f"{k[1]}  {WHITE}{'LIKE ONLY':<22}{RESET} {CYAN}Chỉ làm job like video{RESET}",
            f"{k3}  {GREEN}{'MIXED MODE':<22}{RESET} {CYAN}Kết hợp Follow + Like{RESET}",
        ]
        _frame("CHẾ ĐỘ JOB TIKTOK", rows)


def render_saved_config_menu():
    """Menu hỏi dùng lại cấu hình đã lưu hay cài đặt lại."""
    if HAS_RICH and console:
        _rich_menu("CẤU HÌNH NÀY LẦN?", [
            ("1", "Dùng cũ",   "Giữ nguyên mọi cài đặt trong config.json"),
            ("2", "Cài lại",   "Nhập lại từ đầu: tài khoản, số job, delay, anti-ban"),
        ])
    else:
        k1, k2 = f"{YELLOW}[1]{RESET}", f"{YELLOW}[2]{RESET}"
        n1, n2 = f"{WHITE}{'Dùng cũ':<22}{RESET}", f"{GREEN}{'Cài lại':<22}{RESET}"
        _frame("CẤU HÌNH NÀY LẦN?", [
            f"{k1}  {n1} {CYAN}Giữ nguyên cài đặt đã lưu{RESET}",
            f"{k2}  {n2} {CYAN}Nhập lại từ đầu (tài khoản, job, delay){RESET}",
        ])


# ════════════════════════════════════════════════════════════════════════
#  4. PREFLIGHT (thiết bị sẵn sàng)
# ════════════════════════════════════════════════════════════════════════

_PREF_STYLE = {
    "Thiết bị": ("bold green", "✓"),
    "Serial":   ("cyan",       "◇"),
    "Android":  ("white",      "◇"),
    "Màn hình": ("bold yellow", "◇"),
}


def render_preflight(title: str, rows) -> None:
    """Bảng nhỏ tóm tắt trạng thái sẵn sàng. `rows`: (label, value) với value là text thuần."""
    if HAS_RICH and console:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold cyan", justify="right", width=12)
        grid.add_column(style="white")
        for label, value in rows:
            style, icon = _PREF_STYLE.get(str(label), ("white", "◇"))
            grid.add_row(
                f"{icon}  {label}",
                f"[{style}]{strip_ansi(str(value))}[/{style}]",
            )
        console.print(
            Panel(
                grid,
                title=f"[bold green]✔ {title}[/bold green]",
                border_style="green",
                box=box.ROUNDED,
                expand=False,
                padding=(0, 2),
            )
        )
    else:
        pairs = []
        for label, value in rows:
            label_s = str(label)
            icon = _PREF_STYLE.get(label_s, ("white", "◇"))[1]
            style = _PREF_STYLE.get(label_s, (None, "◇"))[0]
            ansi = {"bold green": GREEN + BOLD, "cyan": CYAN,
                    "white": WHITE, "bold yellow": YELLOW + BOLD}.get(style or "", "")
            pairs.append(
                f"{icon}  {CYAN}{label_s:<12}{RESET}{ansi}{strip_ansi(str(value))}{RESET}"
            )
        _frame(f"✔ {title}", pairs)


# ════════════════════════════════════════════════════════════════════════
#  5. BẢNG TÀI KHOẢN LIÊN KẾT
# ════════════════════════════════════════════════════════════════════════

def render_accounts_table(platform_name: str, accounts: List[Dict[str, Any]], default_idx: int = 1):
    """Danh sách tài khoản đã liên kết (bảng zebra, badge trạng thái)."""
    if HAS_RICH and console:
        table = Table(
            box=box.ROUNDED,
            safe_box=False,
            border_style="cyan",
            padding=(0, 1),
            header_style="bold white on #0e7490",
        )
        table.add_column("#", style="bold yellow", justify="center")
        table.add_column("Tài khoản", style="bold white")
        table.add_column("ID F4F", style="cyan", justify="center")
        table.add_column("Trạng thái", justify="center")
        table.add_column("Ghi chú", style="bold green", justify="center")

        for idx, acc in enumerate(accounts, start=1):
            name = acc.get("username") or acc.get("name") or "N/A"
            acc_id = str(acc.get("id", ""))
            status = str(acc.get("status") or "Hoạt động").strip()
            status_ok = status.lower() in ("hoạt động", "active", "đang hoạt động")
            dot, style = ("●", "bold green") if status_ok else ("◌", "bold yellow")
            badge = f"[{style}]{dot} {status}[/{style}]"
            star = "[bold green]★ Mặc định[/bold green]" if idx == default_idx else ""
            row_style = "dim" if idx % 2 == 0 else None
            table.add_row(
                f"{idx:02}", f"@{name}", acc_id, badge, star, style=row_style
            )

        console.print()
        console.rule(
            f"[bold cyan]TÀI KHOẢN {platform_name.upper()} ĐÃ LIÊN KẾT[/bold cyan]",
            style="cyan",
        )
        console.print(table)
    else:
        # Fallback: tính độ rộng cột động cho thẳng hàng
        names = [(a.get("username") or a.get("name") or "N/A") for a in accounts]
        ids = [str(a.get("id", "")) for a in accounts]
        w_name = max(max(map(len, names)) + 1, 6)
        w_id = max(max(map(len, ids)) + 1, 4)
        rows = []
        for idx, acc in enumerate(accounts, start=1):
            name = names[idx - 1]
            status = str(acc.get("status") or "Hoạt động").strip()
            status_ok = status.lower() in ("hoạt động", "active", "đang hoạt động")
            dot, dot_c = ("●", GREEN) if status_ok else ("◌", YELLOW)
            star = f"{GREEN}★ Mặc định{RESET}" if idx == default_idx else ""
            rows.append(
                f"{YELLOW}[{idx:02}]{RESET}  "
                f"{WHITE}@{name:<{w_name - 1}}{RESET} "
                f"{CYAN}{ids[idx - 1]:<{w_id}}{RESET} "
                f"{dot_c}{dot} {status}{RESET}  {star}"
            )
        _frame(f"TÀI KHOẢN {platform_name.upper()} ĐÃ LIÊN KẾT", rows)


# ════════════════════════════════════════════════════════════════════════
#  6. BÁO CÁO CUỐI PHIÊN
# ════════════════════════════════════════════════════════════════════════

_SUMMARY_ROWS = [
    ("✓", "Follow thành công",  "followed",      GREEN,  "bold green"),
    ("♥", "Like thành công",    "liked",         YELLOW, "bold magenta"),
    ("●", "Đã thực hiện trước", "already",       YELLOW, "yellow"),
    ("↷", "Đã bỏ qua",          "skipped",       CYAN,   "dim yellow"),
    ("!", "Lỗi",                "errors",        RED,    "bold red"),
]


def render_summary_report(platform_name: str, stats: Dict[str, Any], log_file: str):
    """Báo cáo kết quả phiên chạy có bar trực quan + tổng số & coin nổi bật."""
    s = stats
    total = s["followed"] + s["liked"] + s["already"] + s["skipped"] + s["errors"]

    if HAS_RICH and console:
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("L", width=1, justify="center")
        table.add_column("Trạng thái", style="white", width=22)
        table.add_column("Số lượng", justify="right", width=8)
        table.add_column("Bar", justify="left", width=12)

        for icon, label, key, _f, rich_style in _SUMMARY_ROWS:
            count = s[key]
            table.add_row(
                f"[{rich_style}]{icon}[/{rich_style}]",
                f"[{rich_style}]{label}[/{rich_style}]",
                f"[{rich_style}]{count}[/{rich_style}]",
                f"[{rich_style}]{_bar(count, total, 8)}[/{rich_style}]",
            )
        table.add_section()
        table.add_row(
            "", "[bold white]Tổng job xử lý[/bold white]",
            f"[bold white]{total}[/bold white]",
            f"[bold cyan]{_bar(total, total, 8)}[/bold cyan]",
        )
        table.add_row(
            "", "[bold white]Coin nhận được[/bold white]",
            f"[bold bright_yellow]~{s['coins_earned']} xu[/bold bright_yellow]",
            "[dim]💰[/dim]",
        )

        panel = Panel(
            table,
            title=f"[bold cyan]SESSION REPORT — {platform_name.upper()}[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            expand=False,
            padding=(0, 1),
        )
        console.print()
        console.print(panel)
        console.print(f"[dim]File log chi tiết: {log_file}[/dim]\n")
    else:
        rows = []
        for icon, label, key, color, _s in _SUMMARY_ROWS:
            count = s[key]
            lab = label[:20].ljust(20)
            bar_col = color if COLOR_ON else ""
            rows.append(
                f"  {color}{icon}{RESET} {WHITE}{lab}{RESET}"
                f"{color}{count:>5}{RESET}  {bar_col}{_bar(count, total, 8)}{RESET}"
            )
        rows.append(None)
        lab_t = "Tổng job xử lý".ljust(20)
        rows.append(
            f"  {WHITE}{lab_t}{RESET}{WHITE}{total:>5}{RESET}  "
            f"{CYAN if COLOR_ON else ''}{_bar(total, total, 8)}{RESET}"
        )
        lab_c = "Coin nhận được".ljust(20)
        rows.append(
            f"  {WHITE}{lab_c}{RESET}{GREEN}~{s['coins_earned']:>4} xu{RESET}"
        )
        _frame(f"SESSION REPORT — {platform_name.upper()}", rows)
        print(f"\nFile log chi tiết: {log_file}\n")
