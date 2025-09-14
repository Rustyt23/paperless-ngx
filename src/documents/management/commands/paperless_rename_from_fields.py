from __future__ import annotations

import tqdm
from django.core.management.base import BaseCommand

from documents.management.commands.mixins import ProgressBarMixin
from documents.models import Document
from documents.utils.rename_from_custom_fields import compute_title


class Command(ProgressBarMixin, BaseCommand):
    help = "Recompute document titles from 'Vendor Name' and 'Invoice Date' fields."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Process all documents")
        self.add_argument_progress_bar_mixin(parser)

    def handle(self, *args, **options):
        if not options["all"]:
            self.stderr.write("Specify --all to process documents")
            return
        self.handle_progress_bar_mixin(**options)
        for document in tqdm.tqdm(Document.objects.all(), disable=self.no_progress_bar):
            new_title = compute_title(document)
            if new_title and document.title != new_title:
                document.title = new_title
                document.save(update_fields=["title"])
