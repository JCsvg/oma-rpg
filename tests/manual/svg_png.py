"""SVG do Textual para PNG com rsvg-convert, como nas capturas do oma-spotify e do oma-mail.

Troca a fonte pela JetBrainsMono Nerd Font, transforma &#160; em espaço e marca xml:space="preserve"
(sem isso o rsvg come o espaço do começo de cada trecho e as colunas se juntam).
"""

import re
import subprocess
import sys
from pathlib import Path


def converter(svg: str, png: Path, largura: int | None = None) -> None:
    svg = re.sub(r'font-family: "?Fira Code"?[^;]*;', 'font-family: "JetBrainsMono Nerd Font", monospace;', svg)
    svg = svg.replace("&#160;", " ")
    svg = svg.replace("<svg ", '<svg xml:space="preserve" ', 1)
    tmp = png.with_suffix(".tmp.svg")
    tmp.write_text(svg)
    args = ["rsvg-convert", str(tmp), "-o", str(png)]
    if largura:
        args[1:1] = ["-w", str(largura)]
    subprocess.run(args, check=True)
    tmp.unlink()


if __name__ == "__main__":
    converter(Path(sys.argv[1]).read_text(), Path(sys.argv[2]))
