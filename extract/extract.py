import os
import sys
import argparse
from typing import Dict, List, Tuple

# from subprocess import Popen, PIPE, STDOUT
# from pipes import quote as shell_quote

import fitz

# from ... import uis
from ...plugins import PapersPlugin
from ...events import PaperChangeEvent, PostCommandEvent

from ... import repo
from ...utils import resolve_citekey_list
from ...content import write_file



class ExtractPlugin(PapersPlugin):
    """Make the pubs repository also a git repository.

    The git plugin creates a git repository in the pubs directory
    and commit the changes to the pubs repository.

    It also add the `pubs git` subcommand, so git commands can be executed
    in the git repository from the command line.
    """

    name = "extract"
    description = "Extract annotations from pubs documents"

    def __init__(self, conf, ui):
        pass
        self.ui = ui
        self.repository = repo.Repository(conf)
        self.pubsdir = os.path.expanduser(conf["main"]["pubsdir"])
        self.broker = self.repository.databroker

        self.quiet = conf["plugins"].get("extract", {}).get("quiet", False)
        # self.manual = conf['plugins'].get('git', {}).get('manual', False)
        # self.force_color = conf['plugins'].get('git', {}).get('force_color', True)
        # self.list_of_changes = []

    def update_parser(self, subparsers, conf):
        """Allow the usage of the pubs git subcommand"""
        # TODO option for quiet/loud mode.
        # TODO option for ignoring missing documents or erroring.
        extract_parser = subparsers.add_parser(self.name, help=self.description)
        extract_parser.add_argument(
            "citekeys",
            nargs=argparse.REMAINDER,
            help="citekey(s) of the documents to extract from",
        )
        # TODO option for writing to stdout or notes
        extract_parser.add_argument(
            "-w",
            "--write",
            help="write to individual notes instead of standard out. CAREFUL: OVERWRITES NOTES CURRENTLY",
            action='store_true',
            default=None,
        )
        extract_parser.add_argument(
            "-e",
            "--edit",
            help="open each note in editor for manual editing after extracting annotations to it",
            action='store_true',
            default=False,
        )
        extract_parser.set_defaults(func=self.command)

    def command(self, conf, args):
        """Run the annotation extraction"""
        citekeys = resolve_citekey_list(
            self.repository, conf, args.citekeys, ui=self.ui, exit_on_fail=True
        )
        if not citekeys:
            return
        papers = self.gather_papers(citekeys)
        all_annotations = self.extract(papers)
        if args.write:
            self.to_notes(conf, all_annotations, args.edit)
        else:
            self.to_stdout(all_annotations)
        self.repository.close()

    def extract(self, papers):
        papers_annotated = []
        for paper in papers:
            file = self.get_file(paper)
            try:
                papers_annotated.append((paper, self.get_annotations(file)))
            except fitz.FileDataError as e:
                print(f"ERROR: Document {file} is broken: {e}")
        return papers_annotated

    def gather_papers(self, citekeys):
        papers = []
        for key in citekeys:
            papers.append(self.repository.pull_paper(key))
        return papers

    def get_file(self, paper):
        path = self.broker.real_docpath(paper.docpath)
        if not path:
            self.ui.error(f"{paper.citekey} has no valid document.")
        return path

    def get_annotations(self, filename):
        annotations = []
        with fitz.Document(filename) as doc:
            for page in doc:
                for annot in page.annots():
                    content = annot.get_text() or annot.info["content"].replace(
                        "\n", ""
                    )
                    if content:
                        annotations.append(f"[{page.number}] {content}")
        return annotations

    def to_stdout(self, annotated_papers):
        for contents in annotated_papers:
            paper = contents[0]
            annotations = contents[1]
            if annotations:
                print(f"{paper.citekey}")
                for annot in annotations:
                    print(f'> "{annot}"')
                print("")

    def to_notes(self, conf, annotated_papers, edit=False):
        for contents in annotated_papers:
            paper = contents[0]
            annotations = contents[1]
            if annotations:
                notepath = self.broker.real_notepath(
                    paper.citekey, conf["main"]["note_extension"]
                )
                output = "# Annotations\n\n"
                for annotation in annotations:
                    output+=f"> {annotation}\n\n"
                write_file(notepath, output, 'w')
                if edit is True:
                    self.ui.edit_file(notepath, temporary=False)
                # TODO implement NoteEvent(citekey).send()


@PaperChangeEvent.listen()
def paper_change_event(event):
    """When a paper is changed, commit the changes to the directory."""
    pass
    # if ExtractPlugin.is_loaded():
    #     git = ExtractPlugin.get_instance()
    #     if not git.manual:
    #         event_desc = event.description
    #         for a, b in [('\\', '\\\\'), ('"', '\\"'), ('$', '\\$'), ('`', '\\`')]:
    #             event_desc = event_desc.replace(a, b)
    #         git.list_of_changes.append(event_desc)


@PostCommandEvent.listen()
def git_commit(event):
    pass
    # if ExtractPlugin.is_loaded():
    #     try:
    #         extract = ExtractPlugin.get_instance()
    #         if len(extract.list_of_changes) > 0:
    #             if not extract.manual:
    #                 title = ' '.join(sys.argv) + '\n'
    #                 message = '\n'.join([title] + extract.list_of_changes)
    #
    #                 extract.shell('add .')
    #                 extract.shell('commit -F-', message.encode('utf-8'))
    #     except RuntimeError as exc:
    #         uis.get_ui().warning(exc.args[0])
