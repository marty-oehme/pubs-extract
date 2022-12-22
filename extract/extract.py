import os
import argparse

import fitz
import Levenshtein

from pubs.plugins import PapersPlugin
from pubs.events import DocAddEvent, NoteEvent

from pubs import repo
from pubs.utils import resolve_citekey_list
from pubs.content import check_file, read_text_file, write_file


class ExtractPlugin(PapersPlugin):
    """Extract annotations from any pdf document.

    The extract plugin allows manual or automatic extraction of all annotations
    contained in the pdf documents belonging to entries of the pubs library.

    It can write those changes to stdout or directly create and update notes
    for the pubs entries.

    It adds a `pubs extract` subcommand through which it is invoked, but can
    optionally run whenever a new document is imported for a pubs entry.
    """

    name = "extract"
    description = "Extract annotations from pubs documents"

    def __init__(self, conf, ui):
        self.ui = ui
        self.note_extension = conf["main"]["note_extension"]
        self.repository = repo.Repository(conf)
        self.pubsdir = os.path.expanduser(conf["main"]["pubsdir"])
        self.broker = self.repository.databroker

        # TODO implement custom annotation formatting, akin to main config citekey format
        # e.g. `> [{page}] {annotation}`
        # or `:: {annotation} :: {page} ::`
        # and so on
        self.onimport = conf["plugins"].get("extract", {}).get("onimport", False)
        self.minimum_similarity = conf["plugins"].get("extract", {}).get("minimum_similarity", 0.75)

    def update_parser(self, subparsers, conf):
        """Allow the usage of the pubs extract subcommand"""
        # TODO option for ignoring missing documents or erroring.
        extract_parser = subparsers.add_parser(self.name, help=self.description)
        extract_parser.add_argument(
            "citekeys",
            nargs=argparse.REMAINDER,
            help="citekey(s) of the documents to extract from",
        )
        extract_parser.add_argument(
            "-w",
            "--write",
            help="Write to individual notes instead of standard out. Appends to existing notes.",
            action="store_true",
            default=None,
        )
        extract_parser.add_argument(
            "-e",
            "--edit",
            help="Open each note in editor for manual editing after extracting annotations to it.",
            action="store_true",
            default=False,
        )
        extract_parser.set_defaults(func=self.command)

    def command(self, conf, args):
        """Run the annotation extraction command."""
        citekeys = resolve_citekey_list(
            self.repository, conf, args.citekeys, ui=self.ui, exit_on_fail=True
        )
        if not citekeys:
            return
        all_annotations = self.extract(citekeys)
        if args.write:
            self._to_notes(all_annotations, self.note_extension, args.edit)
        else:
            self._to_stdout(all_annotations)
        self.repository.close()

    def extract(self, citekeys):
        """Extracts annotations from citekeys.

        Returns all annotations belonging to the papers that
        are described by the citekeys passed in.
        """
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
        """Get all papers for citekeys.

        Returns all Paper objects described by the citekeys
        passed in.
        """
        papers = []
        for key in citekeys:
            papers.append(self.repository.pull_paper(key))
        return papers

    def _get_file(self, paper):
        """Get path of document belonging to paper.

        Returns the real path to the document which belongs
        to the paper passed in. Emits a warning if no
        document belongs to paper.
        """
        path = self.broker.real_docpath(paper.docpath)
        if not path:
            self.ui.warning(f"{paper.citekey} has no valid document.")
        return path

    def _get_annotations(self, filename):
        """Extract annotations from a file.

        Returns all readable annotations contained in the file
        passed in. Only returns Highlight or Text annotations
        currently.
        """
        annotations = []
        with fitz.Document(filename) as doc:
            for page in doc:
                for annot in page.annots():
                    content = self._retrieve_annotation_content(page, annot)
                    if content:
                        annotations.append(f"[{(page.number or 0) + 1}] {content}")
        return annotations

    def _retrieve_annotation_content(self, page, annotation, connector = "\nNote: "):
        """Gets the text content of an annotation.

        Returns the actual content of an annotation. Sometimes
        that is only the written words, sometimes that is only
        annotation notes, sometimes it is both. Runs a similarity
        comparison between strings to find out whether they
        should both be included or are doubling up.
        """
        content = annotation.info["content"].replace("\n", " ")
        written = page.get_textbox(annotation.rect).replace("\n", " ")

        if Levenshtein.ratio(content,written) > self.minimum_similarity:
            return content
        elif content:
            return f"{written}{connector}{content}"
        return written

    def _to_stdout(self, annotated_papers):
        """Write annotations to stdout.

        Simply outputs the gathered annotations over stdout
        ready to be passed on through pipelines etc.
        """
        output = ""
        for contents in annotated_papers:
            paper = contents[0]
            annotations = contents[1]
            if annotations:
                output += f"{paper.citekey}\n"
                for annot in annotations:
                    output += f'> "{annot}"\n'
                output += "\n"
        print(output)

    def _to_notes(self, annotated_papers, note_extension="txt", edit=False):
        """Write annotations into pubs notes.

        Permanently writes the given annotations into notes
        in the pubs notes directory. Creates new notes for
        citekeys missing a note or appends to existing.
        """
        for contents in annotated_papers:
            paper = contents[0]
            annotations = contents[1]
            if annotations:
                notepath = self.broker.real_notepath(paper.citekey, note_extension)
                if check_file(notepath, fail=False):
                    self._append_to_note(notepath, annotations)
                else:
                    self._write_new_note(notepath, annotations)
                self.ui.info(f"Wrote annotations to {paper.citekey} note {notepath}.")

                if edit is True:
                    self.ui.edit_file(notepath, temporary=False)
                NoteEvent(paper.citekey).send()

    def _write_new_note(self, notepath, annotations):
        """Create a new note containing the annotations.

        Will create a new note in the notes folder of pubs
        and fill it with the annotations extracted from pdf.
        """
        output = "# Annotations\n\n"
        for annotation in annotations:
            output += f"> {annotation}\n\n"
        write_file(notepath, output, "w")

    def _append_to_note(self, notepath, annotations):
        """Append new annotations to the end of a note.

        Looks through note to determine any new annotations which should be
        added and adds them to the end of the note file.
        """
        existing = read_text_file(notepath)
        # removed annotations already found in the note
        existing_dropped = [x for x in annotations if x not in existing]
        if not existing_dropped:
            return

        output = ""
        for annotation in existing_dropped:
            output += f"> {annotation}\n\n"
        write_file(notepath, output, "a")


@DocAddEvent.listen()
def modify_event(event):
    if ExtractPlugin.is_loaded():
        plg = ExtractPlugin.get_instance()
        if plg.onimport:
            all_annotations = plg.extract([event.citekey])
            if all_annotations[0][1]:
                plg._to_notes(all_annotations, plg.note_extension)
                plg.ui.info(f"Imported {event.citekey} annotations.")
