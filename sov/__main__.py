#!/usr/bin/env python3
"""sov — Sovereign Stack entry point"""
import sys, threading

def main():
    from sov.launch import boot
    args = sys.argv[1:]
    fast = "--fast" in args or "-f" in args
    args = [a for a in args if a not in ("--fast", "-f")]

    flags = {a.lower() for a in args}

    if flags & {"--help", "-h", "help"}:
        boot(skip_anim=True)
        return

    if flags & {"--ide", "ide"}:
        boot(skip_anim=fast)
        from sov.ide import main as ide_main
        ide_main(); return

    if flags & {"--womb", "womb", "--ggufwomb", "ggufwomb"}:
        boot(skip_anim=fast)
        from sov.ggufwomb import main as womb_main
        womb_main(); return

    if flags == {"--ui"} or flags == {"-ui"}:
        boot(skip_anim=fast)
        from sov.ui import main as ui_main
        ui_main(open_browser=True); return

    # --cli or default
    with_ui = "--ui" in flags or "-ui" in flags
    passthrough = [a for a in args if a.lower() not in
                   ("--cli", "--ui", "-ui", "-cli")]
    boot(skip_anim=fast)

    if with_ui:
        from sov.ui import main as ui_main
        threading.Thread(target=ui_main,
                         kwargs={"open_browser": True},
                         daemon=True).start()

    from sov.cli import main as cli_main
    sys.argv = [sys.argv[0]] + list(passthrough)
    cli_main()

if __name__ == "__main__":
    main()


