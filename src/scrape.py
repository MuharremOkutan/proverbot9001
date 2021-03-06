#!/usr/bin/env python3.7
##########################################################################
#
#    This file is part of Proverbot9001.
#
#    Proverbot9001 is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Proverbot9001 is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Proverbot9001.  If not, see <https://www.gnu.org/licenses/>.
#
#    Copyright 2019 Alex Sanchez-Stern and Yousef Alhessi
#
##########################################################################

import subprocess
import argparse
import multiprocessing
import tempfile
import functools
import sys
import contextlib
import os

import linearize_semicolons
import serapi_instance

from sexpdata import *
from traceback import *
from util import *
from format import format_context, format_tactic

from typing import Dict, Any, TextIO, List

def main():
    # Parse the command line arguments.
    parser = argparse.ArgumentParser(description="scrape a proof")
    parser.add_argument('-o', '--output', help="output data file name", default=None)
    parser.add_argument('-j', '--threads', default=1, type=int)
    parser.add_argument('-c', '--continue', dest='cont', default=False, const=True, action='store_const')
    parser.add_argument('--hardfail', default=False, const=True, action='store_const')
    parser.add_argument('--prelude', default=".")
    parser.add_argument('-v', '--verbose', default=False, const=True, action='store_const')
    parser.add_argument('--debug', default=False, const=True, action='store_const')
    parser.add_argument("--progress", "-P", help="show progress of files",
                        action='store_const', const=True, default=False)
    parser.add_argument('--skip-nochange-tac', default=False, const=True, action='store_const',
                    dest='skip_nochange_tac')
    parser.add_argument('inputs', nargs="+", help="proof file name(s) (*.v)")
    args = parser.parse_args()


    includes=subprocess.Popen(['make', '-C', args.prelude, 'print-includes'],
                              stdout=subprocess.PIPE).communicate()[0]\
                       .strip().decode('utf-8')

    thispath = os.path.dirname(os.path.abspath(__file__))
    # Set up the command which runs sertop.
    coqargs = ["sertop"]
    with multiprocessing.Pool(args.threads) as pool:
        scrape_result_files = pool.imap_unordered(
            functools.partial(scrape_file, coqargs, args, includes),
            enumerate(args.inputs))
        with (open(args.output, 'w') if args.output
              else contextlib.nullcontext(sys.stdout)) as out:
            for idx, scrape_result_file in enumerate(scrape_result_files, start=1):
                if scrape_result_file is None:
                    eprint("Failed file {} of {}".format(idx, len(args.inputs)))
                else:
                    if args.verbose:
                        eprint("Finished file {} of {}".format(idx, len(args.inputs)))
                    with open(scrape_result_file, 'r') as f:
                        for line in f:
                            out.write(line)

from tqdm import tqdm
def scrape_file(coqargs : List[str], args : argparse.Namespace, includes : str,
                file_tuple : Tuple[int, str]) -> str:
    file_idx, filename = file_tuple
    full_filename = args.prelude + "/" + filename
    result_file = full_filename + ".scrape"
    if args.cont:
        with contextlib.suppress(FileNotFoundError):
            with open(result_file, 'r') as f:
                if args.verbose:
                    eprint(f"Found existing scrape at {result_file}! Using it")
                return result_file
    try:
        commands = serapi_instance.try_load_lin(args, file_idx, full_filename)
        if not commands:
            commands = linearize_semicolons.preprocess_file_commands(
                args, file_idx,
                serapi_instance.load_commands(full_filename),
                coqargs, includes, full_filename, filename, args.skip_nochange_tac)
            serapi_instance.save_lin(commands, full_filename)

        with serapi_instance.SerapiContext(coqargs, includes, args.prelude) as coq:
            coq.debug = args.debug
            try:
                with open(result_file, 'w') as f:
                    for command in tqdm(commands, file=sys.stdout,
                                        disable=(not args.progress),
                                        position=file_idx * 2,
                                        desc="Scraping file", leave=False,
                                        dynamic_ncols=True, bar_format=mybarfmt):
                        process_statement(coq, command, f)
            except serapi_instance.TimeoutError:
                eprint("Command in {} timed out.".format(filename))
            return result_file
    except Exception as e:
        eprint("FAILED: In file {}:".format(filename))
        eprint(e)
        if args.hardfail:
            raise e

def process_statement(coq : serapi_instance.SerapiInstance, command : str,
                      result_file : TextIO) -> None:
    if not re.match("\s*[{}]\s*", command):
        if coq.proof_context:
            prev_tactics = coq.prev_tactics
            prev_hyps = coq.hypotheses
            prev_goal = coq.goals
            result_file.write(format_context(prev_tactics, prev_hyps, prev_goal, ""))
            result_file.write(format_tactic(command))
        else:
            subbed_command = re.sub(r"\n", r"\\n", command)
            result_file.write(subbed_command+"\n-----\n")
    coq.run_stmt(command)

if __name__ == "__main__":
    main()
