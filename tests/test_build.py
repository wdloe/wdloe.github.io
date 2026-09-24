import csv
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('build', Path(__file__).resolve().parents[1] / 'scripts/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

def feed(rows):
    out=io.StringIO()
    writer=csv.DictWriter(out,fieldnames=build.FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()

def row(**changes):
    data=dict.fromkeys(build.FIELDS,'')
    data.update(type='project',title='Project, with punctuation',featured='FALSE',published='TRUE')
    data.update(changes)
    return data

class ContentTests(unittest.TestCase):
    def test_automatic_numbering_is_per_category_newest_first(self):
        records=[row(type='publication',title='Older journal',category='Journal',date='2024'),row(type='publication',title='Conference',category='Conference',date='2025'),row(type='publication',title='New journal',category='Journal',date='2025'),row(type='publication',title='Poster',category='Poster',date='2023')]
        numbered=build.number_publications(records)
        self.assertEqual({r['title']:r['label'] for r in numbered},{'Older journal':'J1','New journal':'J2','Conference':'C1','Poster':'P1'})
        newer=row(type='publication',title='Newest journal',category='Journal',date='2026')
        updated=build.number_publications([newer]+records)
        self.assertEqual(updated[0]['label'],'J3')
        self.assertEqual(next(r['label'] for r in updated if r['title']=='Older journal'),'J1')

    def test_same_year_respects_sheet_order(self):
        records=[row(type='publication',title=title,category='Journal',date='2025') for title in ['Latest','Earlier']]
        self.assertEqual([r['label'] for r in build.number_publications(records)],['J2','J1'])

    def test_old_id_column_is_optional_and_ignored(self):
        legacy='type,id,title,category,date,description,url,image,featured,published\npublication,j99,Paper,Journal,2025,,,,FALSE,TRUE\n'
        records=build.parse_content(legacy)
        self.assertNotIn('id',records[0])
        self.assertEqual(build.number_publications(records)[0]['label'],'J1')

    def test_csv_quotes_unicode_and_multiline(self):
        original=row(description='A "quoted" idea\nAcross orbits — and oceans')
        self.assertEqual(build.parse_content('\ufeff'+feed([original])),[original])

    def test_drafts_are_not_rendered(self):
        rows=[row(), row(published='FALSE',title='Unfinished')]
        self.assertEqual(len(build.parse_content(feed(rows))),1)

    def test_duplicates_and_bad_headers_fail(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            build.parse_content(feed([row(),row()]))
        with self.assertRaisesRegex(ValueError,'headers'):
            build.parse_content('<html>Please sign in</html>')

    def test_invalid_dates_and_categories_fail(self):
        for data in [row(type='news',date='2026-13'),row(type='publication',date='26',category='Journal'),row(type='publication',date='2026',category='Article')]:
            with self.assertRaises(ValueError): build.parse_content(feed([data]))

    def test_unsafe_urls_are_rejected(self):
        for url in ['javascript:alert(1)','//evil.example','/\\evil.example','data:text/html,test','http://insecure.example']:
            with self.assertRaises(ValueError): build.parse_content(feed([row(url=url)]))

    def test_html_is_escaped(self):
        rendered=build.cards([row(title='<script>alert(1)</script>',description='<img onerror=alert(1)>')])
        self.assertNotIn('<script>',rendered)
        self.assertIn('&lt;script&gt;',rendered)

    def test_new_project_and_course_render_without_template_edits(self):
        records=build.parse_content(feed([row(),row(type='course',title='New course',description='Another university')]))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'assets').mkdir()
            with patch.object(build,'ROOT',root),patch.object(build,'load_content',return_value=(records,'test')):
                build.build()
            self.assertIn('Project, with punctuation',(root/'_site/projects/index.html').read_text())
            self.assertIn('New course',(root/'_site/teaching/index.html').read_text())

    def test_failed_import_preserves_previous_site(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'_site').mkdir()
            page=root/'_site/index.html'
            page.write_text('Last successful deployment')
            with patch.object(build,'ROOT',root),patch.object(build,'load_content',side_effect=ValueError('Invalid feed')):
                with self.assertRaises(ValueError): build.build()
            self.assertEqual(page.read_text(),'Last successful deployment')

    def test_remote_import_and_local_fallback(self):
        remote=io.BytesIO(feed([row()]).encode())
        with patch.dict('os.environ',{'CONTENT_SHEET_URL':'https://docs.google.com/spreadsheets/d/e/example/pub?output=csv'}),patch.object(build.urllib.request,'urlopen',return_value=remote):
            records,source=build.load_content()
            self.assertEqual(source,'google-sheets')
            self.assertEqual(records[0]['title'],'Project, with punctuation')
        with patch.dict('os.environ',{'CONTENT_SHEET_URL':'','CONTENT_OFFLINE':'1'}):
            records,source=build.load_content()
            self.assertEqual(source,'local')
            self.assertEqual(len([r for r in records if r['type']=='publication']),14)

    def test_saved_sheet_is_used_when_repository_variable_is_unset(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'data').mkdir()
            url='https://docs.google.com/spreadsheets/d/e/example/pub?output=csv'
            (root/'data/source.json').write_text(build.json.dumps({'google_sheet_csv_url':url}))
            with patch.object(build,'ROOT',root),patch.dict('os.environ',{'CONTENT_SHEET_URL':'','CONTENT_OFFLINE':''}),patch.object(build.urllib.request,'urlopen',return_value=io.BytesIO(feed([row()]).encode())) as fetch:
                records,source=build.load_content()
                self.assertEqual(source,'google-sheets')
                self.assertEqual(fetch.call_args.args[0].full_url,url)

if __name__ == '__main__': unittest.main()
