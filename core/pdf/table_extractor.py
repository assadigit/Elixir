"""
Table Extractor – uses Camelot or Tabula to extract tables from PDF pages.
Converts tables to Markdown and inserts them into the markdown content.
"""

from collections.abc import Callable
from pathlib import Path

from utils.logging import get_main_logger

logger = get_main_logger()


class TableExtractor:
    def __init__(
        self,
        log_callback: Callable[[str, str], None] | None = None,
        method: str = "camelot",
    ):
        self.log = log_callback or (lambda msg, level="INFO": None)
        self.method = method
        self._camelot = None
        self._tabula = None

    def _init_camelot(self) -> bool:
        try:
            import camelot

            self._camelot = camelot
            self.log("  ✅ Camelot loaded for table extraction.", "INFO")
            return True
        except ImportError:
            self.log("  ⚠️ Camelot not installed. Run: pip install camelot-py[cv]", "WARNING")
            return False

    def _init_tabula(self) -> bool:
        try:
            import tabula

            self._tabula = tabula
            self.log("  ✅ Tabula loaded for table extraction.", "INFO")
            return True
        except ImportError:
            self.log("  ⚠️ Tabula not installed. Run: pip install tabula-py", "WARNING")
            return False

    def extract_tables_from_pdf(self, pdf_path: Path, pages: str = "all") -> dict[int, list[str]]:
        """
        Extract tables from specified pages.
        Returns dict: page_num -> list of Markdown table strings.
        """
        results = {}
        if self.method == "camelot":
            if not self._init_camelot():
                return results
            try:
                tables = self._camelot.read_pdf(str(pdf_path), pages=pages, flavor="lattice")
                for table in tables:
                    page = table.page
                    md = self._camelot_table_to_markdown(table)
                    if md:
                        results.setdefault(page, []).append(md)
                self.log(f"  📊 Camelot extracted {len(tables)} tables from {pages}", "INFO")
            except Exception as e:
                self.log(f"  ❌ Camelot extraction failed: {e}", "WARNING")
        else:  # tabula
            if not self._init_tabula():
                return results
            try:
                # tabula.read_pdf returns list of DataFrames
                dfs = self._tabula.read_pdf(str(pdf_path), pages=pages, multiple_tables=True)
                for df in dfs:
                    if not df.empty:
                        md = self._dataframe_to_markdown(df)
                        if md:
                            # We don't have page info from tabula easily, we'll assign to current page? Better to skip.
                            # We'll store with page 0 and later merge.
                            results.setdefault(0, []).append(md)
                self.log(f"  📊 Tabula extracted {len(dfs)} tables from {pages}", "INFO")
            except Exception as e:
                self.log(f"  ❌ Tabula extraction failed: {e}", "WARNING")
        return results

    def _camelot_table_to_markdown(self, table) -> str:
        """Convert a Camelot Table object to Markdown."""
        df = table.df
        return self._dataframe_to_markdown(df)

    def _dataframe_to_markdown(self, df) -> str:
        """Convert pandas DataFrame to Markdown table."""
        if df.empty:
            return ""
        # Ensure all columns are strings
        df = df.astype(str)
        # Build header
        headers = df.columns.tolist()
        col_widths = [
            max(len(str(h)), max(len(str(row[i])) for row in df.itertuples(index=False)))
            for i, h in enumerate(headers)
        ]

        def format_row(row, widths):
            return (
                "| " + " | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)) + " |"
            )

        sep = "|" + "|".join("-" * (w + 2) for w in col_widths) + "|"
        lines = []
        lines.append(format_row(headers, col_widths))
        lines.append(sep)
        for row in df.itertuples(index=False):
            lines.append(format_row(row, col_widths))
        return "\n".join(lines)

    def insert_tables_into_markdown(
        self, markdown: str, tables_by_page: dict[int, list[str]]
    ) -> str:
        """
        V9.2.0 M4: Insert table markdown into the main markdown at the
        corresponding page markers (inline), not just appended at the end.
        This ensures the LLM sees tables in context when summarizing.
        """
        if not tables_by_page:
            return markdown

        result = markdown
        uninserted = {}

        for page, table_list in sorted(tables_by_page.items()):
            if page == 0:
                uninserted[page] = table_list
                continue
            marker = f"<!-- original page {page} -->"
            if marker in result:
                tables_text = f"\n### \U0001f4ca Tables from page {page}\n\n"
                for md in table_list:
                    tables_text += md + "\n\n"
                result = result.replace(marker, marker + tables_text, 1)
            else:
                uninserted[page] = table_list

        if uninserted:
            tables_text = "\n\n## Extracted Tables\n\n"
            for page, table_list in sorted(uninserted.items()):
                if page == 0:
                    tables_text += "### Tables (page unknown)\n\n"
                else:
                    tables_text += f"### Tables from page {page}\n\n"
                for md in table_list:
                    tables_text += md + "\n\n"
            result = result + "\n\n" + tables_text

        return result
