from lark import Lark
from pathlib import Path
import argparse
from assembler import Assembler
import sys
from errors import Formatter

DEBUG = False

if DEBUG:
    import traceback


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("infile", help="Input file", type=lambda p: Path(p))
    argparser.add_argument("-o", help="Output file")
    args = argparser.parse_args()

    with open(args.infile) as infile:
        text = infile.read()
        with open("grammar.lark") as grammar:
            parser = Lark(grammar=grammar, start="program", propagate_positions=True, parser="lalr")

            try:
                tree = parser.parse(text)

                if DEBUG:
                    print(tree.pretty())

                assembler = Assembler(text, args.infile)
                assembler.visit(tree)
                code = assembler.machine_code

                if args.o and args.o != "-":
                    with open(args.o, "w") as outfile:
                        for line, _ in code:
                            outfile.write(f"{line:011b}\n")
                else:
                    width = len(str(len(code) - 1))
                    for i, (line, instr) in enumerate(code):
                        print(f"{i:{width}}: {line:011b} -- {instr[0].name.lower()} {instr[1]}")

            except Exception as e:
                if DEBUG:
                    traceback_str = "".join(traceback.format_tb(e.__traceback__))
                    print(traceback_str)
                    print(e)

                print(Formatter.fmt_exc(args.infile, text, e))

                if DEBUG:
                    print(type(e))
                sys.exit(1)


if __name__ == "__main__":
    main()
