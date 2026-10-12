from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import os

def create_pdf(filename, text_lines, folder='tests/fixtures/placement/pdf'):
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)
    c = canvas.Canvas(filepath, pagesize=letter)
    
    y = 750
    for line in text_lines:
        c.drawString(100, y, line)
        y -= 20
        if y < 50:
            c.showPage()
            y = 750
            
    c.save()

# Normal PDF
create_pdf('event_normal.pdf', [
    "Campus Drive by TechCorp Solutions",
    "Role: Software Engineer",
    "CTC: 12 LPA",
    "Eligible Branches: CSE, ECE",
    "Date: 2026-11-20"
])

# Multi-page PDF
create_pdf('event_multipage.pdf', [
    "Campus Drive Notification",
    "Please see next page for details."
] + [""] * 50 + [
    "Company: GlobalTech Services",
    "Role: Backend Engineer",
    "Package: 15 Lakhs",
    "Date: 2026-12-05"
])

# Table PDF (mimicking flattened table)
create_pdf('event_table.pdf', [
    "Campus Drive Table",
    "Company Name | DH Bars & Wires Private Limited",
    "Role | QA Automation Engineer",
    "CTC | 10 LPA",
    "Branches | IT"
])
