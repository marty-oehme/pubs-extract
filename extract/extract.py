import os
import re
import argparse

import fitz
import Levenshtein

from pubs.plugins import PapersPlugin
from pubs.events import DocAddEvent, NoteEvent

from pubs import repo, pretty
from pubs.utils import resolve_citekey_list
from pubs.content import check_file, read_text_file, write_file
from pubs.query import get_paper_filter

CONFIRMATION_PAPER_THRESHOLD=5

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

        self.on_import = conf["plugins"].get("extract", {}).get("on_import", False)
        self.minimum_similarity = float(
            conf["plugins"].get("extract", {}).get("minimum_similarity", 0.75)
        )
        self.formatting = (
            conf["plugins"]
            .get("extract", {})
            .get(
                "formatting",
                "{newline}{quote_begin}> {quote} {quote_end}[{page}]{note_begin}{newline}Note: {note}{note_end}",
            )
        )

    def update_parser(self, subparsers, conf):
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
            self._to_stdout(all_annotations)
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
                papers_annotated.append((paper, self._get_annotations(file)))
            except fitz.FileDataError as e:
                self.ui.error(f"Document {file} is broken: {e}")
        return papers_annotated

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
            for key in keys:
                papers.append(self.repository.pull_paper(key))
        else:
            papers = list(filter(
                get_paper_filter(
                    args.query,
                    case_sensitive=args.case_sensitive,
                    strict=args.strict,
                ),
                self.repository.all_papers(),
            ))
        if len(papers) > CONFIRMATION_PAPER_THRESHOLD:
            self.ui.message('\n'.join(
                pretty.paper_oneliner(p, citekey_only=False, max_authors=conf['main']['max_authors'])
                for p in papers))
            self.ui.input_yn(question=f"Extract annotations for these papers?", default='y')
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
                    annotations.append(
                        self._format_annotation(quote, note, page.number or 0)
                    )
        return annotations

    def _format_annotation(self, quote, note, pagenumber=0):
        output = self.formatting
        replacements = {
            r"{quote}": quote,
            r"{note}": note,
            r"{page}": str(pagenumber),
            r"{newline}": "\n",
        }
        if note == "":
            output = re.sub(r"{note_begin}.*{note_end}", "", output)
        if quote == "":
            output = re.sub(r"{quote_begin}.*{quote_end}", "", output)
        output = re.sub(r"{note_begin}", "", output)
        output = re.sub(r"{note_end}", "", output)
        output = re.sub(r"{quote_begin}", "", output)
        output = re.sub(r"{quote_end}", "", output)
        pattern = re.compile(
            "|".join(
                [re.escape(k) for k in sorted(replacements, key=len, reverse=True)]
            ),
            flags=re.DOTALL,
        )
        return pattern.sub(lambda x: replacements[x.group(0)], output)

    def _retrieve_annotation_content(self, page, annotation):
        """Gets the text content of an annotation.

        Returns the actual content of an annotation. Sometimes
        that is only the written words, sometimes that is only
        annotation notes, sometimes it is both. Runs a similarity
        comparison between strings to find out whether they
        should both be included or are doubling up.
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
                output += f"------ {paper.citekey} ------\n"
                for annot in annotations:
                    output += f"{annot}\n"
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
            output += f"{annotation}\n\n"
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
            output += f"{annotation}\n\n"
        write_file(notepath, output, "a")


@DocAddEvent.listen()
def modify_event(event):
    if ExtractPlugin.is_loaded():
        plg = ExtractPlugin.get_instance()
        if plg.on_import:
            all_annotations = plg.extract([event.citekey])
            if all_annotations[0][1]:
                plg._to_notes(all_annotations, plg.note_extension)
