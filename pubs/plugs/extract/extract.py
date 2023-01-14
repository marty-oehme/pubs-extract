import os
import argparse

import fitz
import Levenshtein

from pubs.plugins import PapersPlugin
from pubs.events import DocAddEvent, NoteEvent
from pubs import repo, pretty
from pubs.utils import resolve_citekey_list
from pubs.content import check_file, read_text_file, write_file
from pubs.query import get_paper_filter
from .annotation import (
    PaperAnnotated,
    Annotation,
    COLOR_SIMILARITY_MINIMUM,
    TEXT_SIMILARITY_MINIMUM,
)

CONFIRMATION_PAPER_THRESHOLD = 5


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
        self.max_authors = conf["main"]["max_authors"]
        self.repository = repo.Repository(conf)
        self.pubsdir = os.path.expanduser(conf["main"]["pubsdir"])
        self.broker = self.repository.databroker

        settings = conf["plugins"].get("extract", {})
        self.on_import = settings.get("on_import", False)
        self.minimum_similarity = float(
            settings.get("minimum_text_similarity", TEXT_SIMILARITY_MINIMUM)
        )
        self.minimum_color_similarity = float(
            settings.get("minimum_color_similarity", COLOR_SIMILARITY_MINIMUM)
        )
        self.formatting = settings.get(
            "formatting",
            "{%quote_container> {quote} %}[{page}]{%note_container{newline}Note: {note} %}{%tag_container #{tag}%}",
        )
        self.color_mapping = settings.get("tags", {})
        self.short_header = settings.get("short_header", False)

    def update_parser(self, subparsers, _):
        """Allow the usage of the pubs extract subcommand"""
        # TODO option for ignoring missing documents or erroring.
        extract_parser = subparsers.add_parser(self.name, help=self.description)
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
        extract_parser.add_argument(
            "-q",
            "--query",
            help="Query library instead of providing individual citekeys. For query help see pubs list command.",
            action="store_true",
            default=None,
            dest="is_query",
        )
        extract_parser.add_argument(
            "-i",
            "--ignore-case",
            action="store_false",
            default=None,
            dest="case_sensitive",
            help="When using query mode, perform case insensitive search.",
        )
        extract_parser.add_argument(
            "-I",
            "--force-case",
            action="store_true",
            dest="case_sensitive",
            help="When using query mode, perform case sensitive search.",
        )
        extract_parser.add_argument(
            "--strict",
            action="store_true",
            default=False,
            help="Force strict unicode comparison of query.",
        )
        extract_parser.add_argument(
            "query",
            nargs=argparse.REMAINDER,
            help="Citekey(s)/query for the documents to extract from.",
        )
        extract_parser.set_defaults(func=self.command)

    def command(self, conf, args):
        """Run the annotation extraction command."""
        papers = self._gather_papers(conf, args)
        all_annotations = self.extract(papers)
        if args.write:
            self._to_notes(all_annotations, self.note_extension, args.edit)
        else:
            self._to_stdout(all_annotations, self.short_header)
        self.repository.close()

    def extract(self, papers):
        """Extracts annotations from citekeys.

        Returns all annotations belonging to the papers that
        are described by the citekeys passed in.
        """
        papers_annotated = []
        for paper in papers:
            file = self._get_file(paper)
            try:
                annotations = self._get_annotations(file)
                papers_annotated.append(PaperAnnotated.from_paper(paper, annotations))
            except fitz.FileDataError as e:
                self.ui.error(f"Document {file} is broken: {e}")
        return papers_annotated

    def tag_from_colorname(self, colorname):
        return self.color_mapping.get(colorname, "")

    def _gather_papers(self, conf, args):
        """Get all papers for citekeys.

        Returns all Paper objects described by the citekeys
        passed in.
        """
        papers = []
        if not args.is_query:
            keys = resolve_citekey_list(
                self.repository, conf, args.query, ui=self.ui, exit_on_fail=True
            )
            if not keys:
                return []
            for key in keys:
                papers.append(self.repository.pull_paper(key))
        else:
            papers = list(
                filter(
                    get_paper_filter(
                        args.query,
                        case_sensitive=args.case_sensitive,
                        strict=args.strict,
                    ),
                    self.repository.all_papers(),
                )
            )
        if len(papers) > CONFIRMATION_PAPER_THRESHOLD:
            self.ui.message(
                "\n".join(
                    pretty.paper_oneliner(
                        p, citekey_only=False, max_authors=self.max_authors
                    )
                    for p in papers
                )
            )
            self.ui.input_yn(
                question=f"Extract annotations for these papers?", default="y"
            )
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
                    quote, note = self._retrieve_annotation_content(page, annot)
                    a = Annotation(
                        file=filename,
                        text=quote,
                        content=note,
                        colors=annot.colors,
                        type=annot.type[1],
                        page=(page.number or 0) + 1,
                    )
                    a.tag = self.tag_from_colorname(a.colorname)
                    annotations.append(a)
        return annotations

    def _retrieve_annotation_content(self, page, annotation):
        """Gets the text content of an annotation.

        Returns the actual content of an annotation. Sometimes
        that is only the written words, sometimes that is only
        annotation notes, sometimes it is both. Runs a similarity
        comparison between strings to find out whether they
        should both be included or are doubling up, using
        Levenshtein distance.
        """
        content = annotation.info["content"].replace("\n", " ")
        written = page.get_textbox(annotation.rect).replace("\n", " ")

        # highlight with selection in note
        if Levenshtein.ratio(content, written) > self.minimum_similarity:
            return (content, "")
        # an independent note, not a highlight
        elif content and not written:
            return ("", content)
        # both a highlight and a note
        elif content:
            return (written, content)
        # highlight with selection not in note
        return (written, "")

    def _to_stdout(self, annotated_papers, short_header=False):
        """Write annotations to stdout.

        Simply outputs the gathered annotations over stdout
        ready to be passed on through pipelines etc.
        """
        output = ""
        for paper in annotated_papers:
            output += f"\n------ {paper.headline(self.short_header, self.max_authors)} ------\n\n"
            for annotation in paper.annotations:
                output += f"{annotation.format(self.formatting)}\n"
                output += "\n"
        self.ui.message(output.strip())

    def _to_notes(self, annotated_papers, note_extension="txt", edit=False):
        """Write annotations into pubs notes.

        Permanently writes the given annotations into notes
        in the pubs notes directory. Creates new notes for
        citekeys missing a note or appends to existing.
        """
        for paper in annotated_papers:
            if paper.annotations:
                notepath = self.broker.real_notepath(paper.citekey, note_extension)
                if check_file(notepath, fail=False):
                    self._append_to_note(notepath, paper)
                else:
                    self._write_new_note(
                        notepath,
                        paper,
                        paper.headline(short=True, max_authors=self.max_authors),
                    )
                self.ui.info(f"Wrote annotations to {paper.citekey} note {notepath}.")

                if edit is True:
                    self.ui.edit_file(notepath, temporary=False)
                NoteEvent(paper.citekey).send()

    def _write_new_note(self, notepath, paper, headline):
        """Create a new note containing the annotations.

        Will create a new note in the notes folder of pubs
        and fill it with the annotations extracted from pdf.
        """
        output = f"# {headline}\n\n"
        for annotation in paper.annotations:
            output += f"{annotation.format(self.formatting)}\n\n"
        write_file(notepath, output, "w")

    def _append_to_note(self, notepath, paper):
        """Append new annotations to the end of a note.

        Looks through note to determine any new annotations which should be
        added and adds them to the end of the note file.
        """
        existing = read_text_file(notepath)
        # removed annotations already found in the note
        existing_dropped = [
            x for x in paper.annotations if x.format(self.formatting) not in existing
        ]
        if not existing_dropped:
            return

        output = ""
        for annotation in existing_dropped:
            output += f"{annotation.format(self.formatting)}\n\n"
        write_file(notepath, output, "a")


@DocAddEvent.listen()
def modify_event(event):
    if ExtractPlugin.is_loaded():
        plg = ExtractPlugin.get_instance()
        if plg.on_import:
            all_annotations = plg.extract([event.citekey])
            if all_annotations[0][1]:
                plg._to_notes(all_annotations, plg.note_extension)
