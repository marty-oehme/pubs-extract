import os
import argparse

# from subprocess import Popen, PIPE, STDOUT
# from pipes import quote as shell_quote

import fitz

from pubs.plugins import PapersPlugin
from pubs.events import DocAddEvent, NoteEvent

from pubs import repo
from pubs.utils import resolve_citekey_list
from pubs.content import write_file



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
        self.ui = ui
        self.conf = conf
        self.repository = repo.Repository(conf)
        self.pubsdir = os.path.expanduser(conf["main"]["pubsdir"])
        self.broker = self.repository.databroker

        self.onimport = conf["plugins"].get("extract", {}).get("onimport", False)
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
        all_annotations = self.extract(citekeys)
        if args.write:
            self._to_notes(all_annotations, conf["main"]["note_extension"], args.edit)
        else:
            self._to_stdout(all_annotations)
        self.repository.close()

    def extract(self, citekeys):
        papers = self._gather_papers(citekeys)
        papers_annotated = []
        for paper in papers:
            file = self._get_file(paper)
            try:
                papers_annotated.append((paper, self._get_annotations(file)))
            except fitz.FileDataError as e:
                self.ui.error(f"Document {file} is broken: {e}")
        return papers_annotated

    def _gather_papers(self, citekeys):
        papers = []
        for key in citekeys:
            papers.append(self.repository.pull_paper(key))
        return papers

    def _get_file(self, paper):
        path = self.broker.real_docpath(paper.docpath)
        if not path:
            self.ui.warning(f"{paper.citekey} has no valid document.")
        return path

    def _get_annotations(self, filename):
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

    def _to_stdout(self, annotated_papers):
        output = ""
        for contents in annotated_papers:
            paper = contents[0]
            annotations = contents[1]
            if annotations:
                output+=f"{paper.citekey}\n"
                for annot in annotations:
                    output+=f'> "{annot}"\n'
                output+="\n"
        print(output)

    def _to_notes(self, annotated_papers, note_extension="txt", edit=False):
        for contents in annotated_papers:
            paper = contents[0]
            annotations = contents[1]
            if annotations:
                notepath = self.broker.real_notepath(
                    paper.citekey, note_extension
                )
                output = "# Annotations\n\n"
                for annotation in annotations:
                    output+=f"> {annotation}\n\n"
                write_file(notepath, output, 'w')
                if edit is True:
                    self.ui.edit_file(notepath, temporary=False)
                NoteEvent(paper.citekey).send()


@DocAddEvent.listen()
def modify_event(event):
    if ExtractPlugin.is_loaded():
        plg = ExtractPlugin.get_instance()
        if plg.onimport:
            all_annotations = plg.extract([event.citekey])
            if all_annotations[0][1]:
                plg._to_notes(all_annotations, plg.conf["main"]["note_extension"])
                plg.ui.info(f"Imported {event.citekey} annotations.")

