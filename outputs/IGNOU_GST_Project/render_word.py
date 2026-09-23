from pathlib import Path
import json
import win32com.client

root=Path(__file__).parent.resolve()
app=win32com.client.DispatchEx('Word.Application')
app.Visible=False
app.DisplayAlerts=0
doc=None
try:
    print('Opening report in Word',flush=True)
    doc=app.Documents.Open(str(root/'Kajal_IGNOU_MCom_GST_Project.docx'),ReadOnly=False,AddToRecentFiles=False)
    print('Repaginating',flush=True)
    doc.Repaginate()
    doc.Fields.Update()
    pages=doc.ComputeStatistics(2)
    print('Rendered pages:',pages,flush=True)
    headings=[]
    manifest=json.loads((root/'page_manifest.json').read_text(encoding='utf-8'))
    for item in manifest:
        name=f"page_{item['page']:03d}"
        if doc.Bookmarks.Exists(name):
            headings.append({'title':item['title'],'planned':item['page'],'page':doc.Bookmarks(name).Range.Information(3)})
    print('Saving and exporting PDF',flush=True)
    (root/'render_audit.json').write_text(json.dumps({'pages':pages,'headings':headings},ensure_ascii=False,indent=2),encoding='utf-8')
    doc.Save()
    doc.ExportAsFixedFormat(str(root/'Kajal_IGNOU_MCom_GST_Project.pdf'),17)
    (root/'render_audit.json').write_text(json.dumps({'pages':pages,'headings':headings},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pages':pages,'page_mismatches':[x for x in headings if x['planned']!=x['page']]},ensure_ascii=True,indent=2))
finally:
    if doc is not None:doc.Close(False)
    app.Quit()
