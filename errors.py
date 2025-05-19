from colorama import Style, Fore
from lark import UnexpectedCharacters, UnexpectedEOF, UnexpectedToken, Token
from exceptions import UnknownLabelException, ImmediateOutOfRangeException
from enum import Enum, auto


class Formatter:
    class Level(Enum):
        ERROR = auto()
        WARNING = auto()
        INFO = auto()

    @staticmethod
    def fmt_exc(file_name: str, text: str, e: Exception):
        match e:
            case UnexpectedCharacters():
                return Formatter.fmt(
                    file_name,
                    text,
                    "unknown directive." if e.char == "." else "unexpected character.",
                    e.line,
                    e.column,
                    e.pos_in_stream,
                )
            case UnexpectedEOF():
                return Formatter.fmt(
                    file_name,
                    text,
                    "unexpected EOF.",
                    e.line,
                    e.column,
                    e.pos_in_stream,
                    e.token,
                )
            case UnexpectedToken():
                if "COMMA" in e.expected:
                    help = ", did you forget a comma?"
                elif "COLON" in e.expected:
                    help = ", did you forget a colon?"
                else:
                    help = "."

                err = Formatter.fmt(
                    file_name,
                    text,
                    f"unexpected token '{e.token}'{help}",
                    e.line,
                    e.column,
                    e.token.start_pos,
                    e.token,
                )

                if help == ".":
                    err += "\n\nexpected one of:\n"
                    for item in e.expected:
                        err += f"   {item}\n"

                return err
            case UnknownLabelException():
                message = f"unexpected label '{e.token}'"
                if e.closest:
                    message += f", did you mean '{e.closest}'?"
                else:
                    message += "."
                return Formatter.fmt(
                    file_name,
                    text,
                    message,
                    e.token.line,
                    e.token.column,
                    e.token.start_pos,
                    e.token,
                )
            case ImmediateOutOfRangeException():
                return Formatter.fmt(
                    file_name,
                    text,
                    "immediate out of range.",
                    e.token.line,
                    e.token.column,
                    e.token.start_pos,
                    e.token,
                )
            case _:
                return Formatter.fmt(
                    file_name,
                    text,
                    str(e),
                    -1,
                    -1,
                    -1,
                )

    @staticmethod
    def fmt(
        file_name: str,
        text: str,
        message: str,
        line: int,
        column: int,
        pos: int,
        token: Token | None = None,
        context_span: int = 120,
        level: Level = Level.ERROR,
    ):
        message = message.encode("unicode_escape").decode("utf-8")
        token_underline = ""
        if token:
            token_span = token.end_pos - token.start_pos
            token_underline = f"{'~' * (token_span - 1)}"

        context_start = max(pos - context_span, 0)
        context_end = pos + context_span
        context_before = text[context_start:pos].rsplit("\n", 1)[-1]
        context_after = text[pos:context_end].split("\n", 1)[0]

        file_and_loc = f"{Style.BRIGHT}{file_name}"
        if line > -1 and column > -1:
            file_and_loc += f":{line}:{column}"

        match level:
            case Formatter.Level.INFO:
                formatted_message = f"{Fore.GREEN}info:{Style.RESET_ALL} {message}"
                context = f"{context_before}{Style.BRIGHT}{Fore.GREEN}{context_after}{Style.RESET_ALL}"
                pointer = f"{' ' * len(context_before.expandtabs())}{Style.BRIGHT}{Fore.GREEN}^{token_underline}{Style.RESET_ALL}"
            case Formatter.Level.WARNING:
                formatted_message = f"{Fore.YELLOW}warning:{Style.RESET_ALL} {message}"
                context = f"{context_before}{Style.BRIGHT}{Fore.YELLOW}{context_after}{Style.RESET_ALL}"
                pointer = f"{' ' * len(context_before.expandtabs())}{Style.BRIGHT}{Fore.YELLOW}^{token_underline}{Style.RESET_ALL}"
            case Formatter.Level.ERROR:
                formatted_message = f"{Fore.RED}error:{Style.RESET_ALL} {message}"
                context = f"{context_before}{Style.BRIGHT}{Fore.RED}{context_after}{Style.RESET_ALL}"
                pointer = f"{' ' * len(context_before.expandtabs())}{Style.BRIGHT}{Fore.RED}^{token_underline}{Style.RESET_ALL}"

        formatted = f"{file_and_loc}: {formatted_message}"
        if line > -1 and column > -1:
            formatted += f"\n    {line} | {context}\n"
            formatted += f"    {' ' * len(str(line))} | {pointer}"

        return formatted
