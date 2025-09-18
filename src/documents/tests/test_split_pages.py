import shutil
import tempfile
from unittest import mock

from django.test import TestCase
from django.test import override_settings

from documents import tasks
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.models import DocumentSource
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import DummyProgressManager
from documents.tests.utils import FileSystemAssertsMixin
from documents.tests.utils import SampleDirMixin


class TestSplitPagesPlugin(
    DirectoriesMixin,
    SampleDirMixin,
    FileSystemAssertsMixin,
    TestCase,
):
    @override_settings(CONSUMER_SPLIT_PDF_ON_UPLOAD=True)
    def test_split_each_page(self):
        test_file = self.SAMPLE_DIR / "double-sided-even.pdf"
        temp_copy = self.dirs.scratch_dir / test_file.name
        shutil.copy(test_file, temp_copy)

        with (
            mock.patch("documents.tasks.ProgressManager", DummyProgressManager),
            mock.patch("documents.tasks.consume_file.delay") as delay_mock,
        ):
            result = tasks.consume_file(
                ConsumableDocument(
                    source=DocumentSource.ConsumeFolder,
                    original_file=temp_copy,
                ),
                DocumentMetadataOverrides(),
            )

        self.assertEqual(result, "Page splitting complete!")
        self.assertEqual(delay_mock.call_count, 2)
        self.assertIsNotFile(temp_copy)

    @override_settings(CONSUMER_SPLIT_PDF_ON_UPLOAD=False)
    def test_split_with_override(self):
        test_file = self.SAMPLE_DIR / "double-sided-even.pdf"
        temp_copy = self.dirs.scratch_dir / test_file.name
        shutil.copy(test_file, temp_copy)

        with (
            mock.patch("documents.tasks.ProgressManager", DummyProgressManager),
            mock.patch("documents.tasks.consume_file.delay") as delay_mock,
        ):
            result = tasks.consume_file(
                ConsumableDocument(
                    source=DocumentSource.ConsumeFolder,
                    original_file=temp_copy,
                ),
                DocumentMetadataOverrides(split_pdf_on_upload=True),
            )

        self.assertEqual(result, "Page splitting complete!")
        self.assertEqual(delay_mock.call_count, 2)
        self.assertIsNotFile(temp_copy)

    @override_settings(CONSUMER_SPLIT_PDF_ON_UPLOAD=True)
    def test_split_runs_pre_consume_script(self):
        test_file = self.SAMPLE_DIR / "double-sided-even.pdf"
        temp_copy = self.dirs.scratch_dir / test_file.name
        shutil.copy(test_file, temp_copy)

        with tempfile.NamedTemporaryFile() as script:
            with (
                override_settings(PRE_CONSUME_SCRIPT=script.name),
                mock.patch("documents.tasks.ProgressManager", DummyProgressManager),
                mock.patch("documents.consumer.run_subprocess") as run_mock,
                mock.patch("documents.tasks.consume_file.delay"),
            ):
                tasks.consume_file(
                    ConsumableDocument(
                        source=DocumentSource.ConsumeFolder,
                        original_file=temp_copy,
                    ),
                    DocumentMetadataOverrides(),
                )

        run_mock.assert_called_once()

        args, _ = run_mock.call_args
        command = args[0]
        env = args[1]

        self.assertEqual(command[0], script.name)
        self.assertEqual(command[1], str(temp_copy))
        self.assertEqual(env["DOCUMENT_SOURCE_PATH"], str(temp_copy))
        self.assertIn("DOCUMENT_WORKING_PATH", env)
