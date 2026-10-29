import os
import sys
from shutil import get_terminal_size


_BANNER = r"""
                                              ,----,
                           ,-.----.         ,/   .`|
               ,---,       \    /  \      ,`   .'  :
       ,---.  '  .' \      |   :    \   ;    ;     / .--.,
      /__./| /  ;    '.    |   |  .\ :.'___,/    ,',--.'  \   ,---.    __  ,-.
 ,---.;  ; |:  :       \   .   :  |: ||    :     | |  | /\/  '   ,'\ ,' ,'/ /|  ,----._,.
/___/ \  | |:  |   /\   \  |   |   \ :;    |.';  ; :  : :   /   /   |'  | |' | /   /  ' /   ,---.
\   ;  \ ' ||  :  ' ;.   : |   : .   /`----'  |  | :  | |-,.   ; ,. :|  |   ,'|   :     |  /     \
 \   \  \: ||  |  ;/  \   \;   | |`-'     '   :  ; |  : :/|'   | |: :'  :  /  |   | .\  . /    /  |
  ;   \  ' .'  :  | \  \ ,'|   | ;        |   |  ' |  |  .''   | .; :|  | '   .   ; ';  |.    ' / |
   \   \   '|  |  '  '--'  :   ' |        '   :  | '  : '  |   :    |;  : |   '   .   . |'   ;   /|
    \   `  ;|  :  :        :   : :        ;   |.'  |  | |   \   \  / |  , ;    `---`-'| |'   |  / |
     :   \ ||  | ,'        |   | :        '---'    |  : \    `----'   ---'     .'__/\_: ||   :    |
      '---" `--''          `---'.|                 |  |,'                      |   :    : \   \  /
                             `---`                 `--'                         \   \  /   `----'
                                                                                 `--`-'
""".strip("\n")

_COMPACT_BANNER = r"""
                                              ,----,
                           ,-.----.         ,/   .`|
               ,---,       \    /  \      ,`   .'  :
       ,---.  '  .' \      |   :    \   ;    ;     /
      /__./| /  ;    '.    |   |  .\ :.'___,/    ,'
 ,---.;  ; |:  :       \   .   :  |: ||    :     |
/___/ \  | |:  |   /\   \  |   |   \ :;    |.';  ;
\   ;  \ ' ||  :  ' ;.   : |   : .   /`----'  |  |
 \   \  \: ||  |  ;/  \   \;   | |`-'     '   :  ;
  ;   \  ' .'  :  | \  \ ,'|   | ;        |   |  '
   \   \   '|  |  '  '--'  :   ' |        '   :  |
    \   `  ;|  :  :        :   : :        ;   |.'
     :   \ ||  | ,'        |   | :        '---'
      '---" `--''          `---'.|
                             `---`  forge
""".strip("\n")

_PALETTE = (
    "\x1b[38;2;0;112;122m",
    "\x1b[38;2;157;55;78m",
    "\x1b[38;2;148;82;0m",
    "\x1b[38;2;52;101;150m",
    "\x1b[38;2;69;119;48m",
    "\x1b[38;2;112;76;139m",
    "\x1b[38;2;0;120;95m",
)
_RESET = "\x1b[0m"


def show_banner(stream=None):
    stream = stream or sys.stdout
    if not stream.isatty():
        return

    columns = get_terminal_size(fallback=(80, 24)).columns
    lines = (_COMPACT_BANNER if columns < 105 else _BANNER).splitlines()
    if "NO_COLOR" in os.environ or os.environ.get("TERM") == "dumb":
        stream.write("\n".join(lines) + "\n\n")
        return

    color_index = 0
    for line in lines:
        for character in line:
            if character == " ":
                stream.write(character)
                continue
            color = _PALETTE[color_index % len(_PALETTE)]
            stream.write(f"{color}{character}{_RESET}")
            color_index += 1
        stream.write("\n")
    stream.write("\n")
